/* SPDX-License-Identifier: MIT
 * Observe public completion results without changing the driver's behavior.
 * No templates, images, device IDs, error messages or scores enter the channel.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <fprint.h>

static void
report (const char *tag)
{
  const char *text = getenv ("FPRINTD_OBSERVER_FD");
  if (!text || !*text) return;
  char *end = NULL;
  errno = 0;
  long value = strtol (text, &end, 10);
  if (errno || *end || value < 3 || value > INT_MAX) return;
  int type = 0;
  socklen_t length = sizeof type;
  if (getsockopt ((int) value, SOL_SOCKET, SO_TYPE, &type, &length) ||
      type != SOCK_SEQPACKET) return;
  /* A missing/full/broken channel withholds the parent's decision. The public
   * API's return value remains unchanged; SIGPIPE must not abort the daemon. */
  (void) send ((int) value, tag, strlen (tag), MSG_DONTWAIT | MSG_NOSIGNAL);
}

gboolean
fp_device_verify_finish (FpDevice *device, GAsyncResult *result, gboolean *match,
                         FpPrint **print, GError **error)
{
  typedef gboolean (*Finish) (FpDevice *, GAsyncResult *, gboolean *, FpPrint **, GError **);
  Finish original = (Finish) dlsym (RTLD_NEXT, "fp_device_verify_finish");
  if (!original) {
    report ("OBSERVER_ERROR\n");
    g_set_error_literal (error, G_IO_ERROR, G_IO_ERROR_FAILED, "Missing reviewed completion function");
    return FALSE;
  }
  gboolean success = original (device, result, match, print, error);
  if (!success || (error && *error)) report ("VERIFY_ERROR\n");
  else if (!match) report ("OBSERVER_ERROR\n");
  else report (*match ? "VERIFY_OK MATCH\n" : "VERIFY_OK NO_MATCH\n");
  return success;
}

gboolean
fp_device_close_finish (FpDevice *device, GAsyncResult *result, GError **error)
{
  typedef gboolean (*Finish) (FpDevice *, GAsyncResult *, GError **);
  Finish original = (Finish) dlsym (RTLD_NEXT, "fp_device_close_finish");
  if (!original) {
    report ("OBSERVER_ERROR\n");
    g_set_error_literal (error, G_IO_ERROR, G_IO_ERROR_FAILED, "Missing reviewed completion function");
    return FALSE;
  }
  gboolean success = original (device, result, error);
  report (success && (!error || !*error) ? "CLOSE_OK\n" : "CLOSE_ERROR\n");
  return success;
}
