/* Offline harness. The runner inserts the actual constructor from the worktree.
 * No USB, driver initialization, TLS handshake, or libfprint library is linked.
 */
#include <glib.h>
#include <openssl/err.h>
#include <openssl/ssl.h>
#include <openssl/sslerr.h>
#include <string.h>

/* INSERT DEVICE ERROR ENUM */

/* Stand-in for libfprint's quark registration, with the same domain name. */
static GQuark
fp_device_error_quark (void)
{
  return g_quark_from_static_string ("fp-device-error-quark");
}
#define FP_DEVICE_ERROR (fp_device_error_quark ())

static gboolean inject;
static unsigned long injected_code, observed_code;
static const char *injected_reason;
static unsigned int reads;

static unsigned long
test_get_error (void)
{
  reads++;
  observed_code = inject ? injected_code : ERR_get_error ();
  return observed_code;
}

static const char *
test_reason (unsigned long code)
{
  g_assert_cmpuint (code, ==, observed_code);
  return inject ? injected_reason : ERR_reason_error_string (code);
}

#define ERR_get_error test_get_error
#define ERR_reason_error_string test_reason
/* INSERT ERROR CONSTRUCTOR */
#undef ERR_get_error
#undef ERR_reason_error_string

int
main (int argc, char **argv)
{
  g_assert_cmpint (argc, ==, 2);
  const char *name = argv[1];
  char *owned = NULL;
  unsigned int iterations = 1;
  ERR_clear_error ();
  inject = TRUE;
  injected_code = 0x12345678;
  injected_reason = "x";
  if (!strcmp (name, "known-openssl"))
    {
      inject = FALSE;
      g_assert_cmpint (OPENSSL_init_ssl (OPENSSL_INIT_LOAD_SSL_STRINGS, NULL), ==, 1);
      ERR_raise (ERR_LIB_SSL, SSL_R_BAD_RECORD_TYPE);
    }
  else if (!strcmp (name, "empty-queue"))
    inject = FALSE;
  else if (!strcmp (name, "unknown-reason"))
    injected_reason = NULL;
  else if (!strcmp (name, "empty-message"))
    injected_reason = "";
  else if (!strcmp (name, "long-message") || !strcmp (name, "repeated"))
    {
      owned = g_malloc0 (8193);
      memset (owned, 'a', 8192);
      memcpy (owned + 4096, "%s%n", 4);
      injected_reason = owned;
      if (!strcmp (name, "repeated"))
        iterations = 1000;
    }
  else
    g_assert_cmpstr (name, ==, "short-message");

  for (unsigned int i = 0; i < iterations; i++)
    {
      reads = 0;
      GError *error = err_from_ssl ();
      g_assert_nonnull (error);
      g_assert_true (g_error_matches (error, FP_DEVICE_ERROR, FP_DEVICE_ERROR_GENERAL));
      g_assert_cmpuint (reads, ==, 1);
      const char *reason = inject ? injected_reason : ERR_reason_error_string (observed_code);
      const char *text = reason ? reason : "OpenSSL provided no error reason";
      char *expected = g_strdup_printf ("TLS error 0x%lx: %s", observed_code, text);
      g_assert_cmpstr (error->message, ==, expected);
      if (!inject && !strcmp (name, "known-openssl"))
        g_assert_nonnull (reason);
      g_assert_cmpuint (ERR_peek_error (), ==, 0);
      GError *copy = g_error_copy (error);
      g_error_free (error);
      g_assert_cmpstr (copy->message, ==, expected);
      g_error_free (copy);
      g_free (expected);
    }
  g_free (owned);
  return 0;
}
