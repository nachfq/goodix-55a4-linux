/* Actual goodixtls implementation with real OpenSSL, sockets and pthreads.
 * Failure shims target resource acquisition; no USB or sensor is available. */
#include <gio/gio.h>
#include <openssl/ssl.h>
#include <openssl/err.h>
#include <pthread.h>
#include <poll.h>
#include <errno.h>
#include <sys/socket.h>
#include <unistd.h>
#include <string.h>
#include <stdlib.h>

#define FP_DEVICE_ERROR G_IO_ERROR
#define FP_DEVICE_ERROR_GENERAL G_IO_ERROR_FAILED
#define GOODIX_TLS_DEADLINE_MS 250
#define fp_dbg(...) ((void)0)

/* INSERT SERVER TYPES */

static guint fail_at, boundary;
static gboolean fail (void) { return fail_at && ++boundary == fail_at; }
static SSL_CTX *test_ctx_new (const SSL_METHOD *m) { return fail () ? NULL : SSL_CTX_new (m); }
static int test_dh (SSL_CTX *c, int x) { return fail () ? 0 : SSL_CTX_set_dh_auto (c, x); }
static int test_cipher (SSL_CTX *c, const char *x) { return fail () ? 0 : SSL_CTX_set_cipher_list (c, x); }
static int test_min (SSL_CTX *c, int x) { return fail () ? 0 : SSL_CTX_set_min_proto_version (c, x); }
static int test_max (SSL_CTX *c, int x) { return fail () ? 0 : SSL_CTX_set_max_proto_version (c, x); }
static int test_socketpair (int a, int b, int c, int *d) { if (fail ()) { errno = EMFILE; return -1; } return socketpair (a,b,c,d); }
static SSL *test_ssl_new (SSL_CTX *c) { return fail () ? NULL : SSL_new (c); }
static int test_set_fd (SSL *s, int fd) { return fail () ? 0 : SSL_set_fd (s,fd); }
static int test_thread (pthread_t *t, const pthread_attr_t *a, void *(*fn)(void*), void *d) { return fail () ? EAGAIN : pthread_create (t,a,fn,d); }
#undef SSL_CTX_set_dh_auto
#undef SSL_CTX_set_min_proto_version
#undef SSL_CTX_set_max_proto_version
#define SSL_CTX_new test_ctx_new
#define SSL_CTX_set_dh_auto test_dh
#define SSL_CTX_set_cipher_list test_cipher
#define SSL_CTX_set_min_proto_version test_min
#define SSL_CTX_set_max_proto_version test_max
#define socketpair test_socketpair
#define SSL_new test_ssl_new
#define SSL_set_fd test_set_fd
#define pthread_create test_thread
/* INSERT TLS IMPLEMENTATION */
#undef SSL_CTX_new
#undef SSL_CTX_set_dh_auto
#undef SSL_CTX_set_cipher_list
#undef SSL_CTX_set_min_proto_version
#undef SSL_CTX_set_max_proto_version
#undef socketpair
#undef SSL_new
#undef SSL_set_fd
#undef pthread_create

static void publish (GoodixTlsServer *s, GError *error, gpointer unused)
{
  s->accept_error = error;
  g_atomic_int_set (&s->accept_result, error ? -1 : 1);
}
static GoodixTlsServer *make_server (void)
{
  GoodixTlsServer *s = g_new0 (GoodixTlsServer, 1);
  s->connection_callback = publish;
  s->sock_fd = s->client_fd = -1;
  return s;
}
static void assert_clean (GoodixTlsServer *s)
{
  g_assert_null (s->ssl_layer); g_assert_null (s->ssl_ctx);
  g_assert_null (s->accept_error); g_assert_false (s->thread_started);
  g_assert_cmpint (s->sock_fd, ==, -1); g_assert_cmpint (s->client_fd, ==, -1);
}
static unsigned int client_psk (SSL *ssl, const char *hint, char *identity,
                               unsigned int id_size, unsigned char *psk, unsigned int size)
{
  g_assert_cmpuint (size, >=, 32); g_assert_cmpuint (id_size, >=, 5);
  memcpy (identity, "test", 5); memset (psk, 0, 32); return 32;
}
static void real_tls (void)
{
  GoodixTlsServer *s = make_server ();
  GError *error = NULL;
  g_assert_true (goodix_tls_server_init (s, &error)); g_assert_no_error (error);
  SSL_CTX *ctx = test_ctx_new (TLS_client_method ());
  g_assert_nonnull (ctx);
  g_assert_cmpint (test_min (ctx, TLS1_2_VERSION), ==, 1);
  g_assert_cmpint (test_max (ctx, TLS1_2_VERSION), ==, 1);
  g_assert_cmpint (test_cipher (ctx, "PSK-AES128-GCM-SHA256:@SECLEVEL=0"), ==, 1);
  SSL_CTX_set_psk_client_callback (ctx, client_psk);
  SSL *ssl = SSL_new (ctx); g_assert_nonnull (ssl);
  g_assert_cmpint (SSL_set_fd (ssl, s->client_fd), ==, 1);
  gint64 deadline = g_get_monotonic_time () + 1000000;
  for (;;)
    {
      int result = SSL_connect (ssl);
      if (result == 1) break;
      int kind = SSL_get_error (ssl, result);
      g_assert_true (kind == SSL_ERROR_WANT_READ || kind == SSL_ERROR_WANT_WRITE);
      g_assert_cmpint (g_get_monotonic_time (), <, deadline);
      struct pollfd fd = {.fd = s->client_fd, .events = kind == SSL_ERROR_WANT_READ ? POLLIN : POLLOUT};
      poll (&fd, 1, 10);
    }
  while (g_atomic_int_get (&s->accept_result) == 0)
    { g_assert_cmpint (g_get_monotonic_time (), <, deadline); g_usleep (1000); }
  g_assert_cmpint (g_atomic_int_get (&s->accept_result), ==, 1);
  guint8 sent[14260], received[14260]; memset (sent, 0x5a, sizeof sent);
  /* Two separate TLS records prove that acquisition cannot assume one read. */
  g_assert_cmpint (SSL_write (ssl, sent, 6000), ==, 6000);
  g_assert_cmpint (SSL_write (ssl, sent + 6000, sizeof sent - 6000), ==, sizeof sent - 6000);
  guint got = 0;
  while (got < sizeof received)
    {
      int count = goodix_tls_server_receive (s, received + got, sizeof received - got, &error);
      g_assert_no_error (error);
      if (count > 0) got += count;
      else { g_assert_cmpint (errno, ==, EAGAIN); g_usleep (1000); }
      g_assert_cmpint (g_get_monotonic_time (), <, deadline);
    }
  g_assert_cmpmem (received, sizeof received, sent, sizeof sent);
  g_assert_false (s->thread_started);
  SSL_free (ssl); SSL_CTX_free (ctx);
  g_assert_true (goodix_tls_server_deinit (s, &error)); g_assert_no_error (error);
  assert_clean (s); g_free (s);
}
static void flight_fragmentation (void)
{
  GoodixTlsServer *s = make_server ();
  int fd[2]; g_assert_cmpint (socketpair (AF_UNIX, SOCK_STREAM|SOCK_NONBLOCK,0,fd), ==,0);
  s->sock_fd = fd[0]; s->client_fd = fd[1];
  guint8 record[] = {22,3,3,0,4,14,0,0,0}, buffer[64];
  for (guint i=0; i<sizeof record; i++)
    {
      g_assert_cmpint (send (fd[0],record+i,1,MSG_NOSIGNAL), ==,1);
      int got = goodix_tls_client_recv (s,buffer,sizeof buffer);
      if (i+1 < sizeof record) { g_assert_cmpint (got, ==,-1); g_assert_cmpint (errno, ==,EAGAIN); }
      else { g_assert_cmpint (got, ==,sizeof record); g_assert_cmpmem (buffer,got,record,sizeof record); }
    }
  guint8 final[] = {20,3,3,0,1,1,22,3,3,0,3,42,42,42};
  g_assert_cmpint (send(fd[0],final,sizeof final,MSG_NOSIGNAL), ==,sizeof final);
  g_assert_cmpint (goodix_tls_client_recv (s,buffer,sizeof buffer), ==,sizeof final);
  guint8 malformed[] = {22,3,3,0xff,0xff};
  g_assert_cmpint (send(fd[0],malformed,sizeof malformed,MSG_NOSIGNAL), ==,sizeof malformed);
  g_assert_cmpint (goodix_tls_client_recv (s,buffer,sizeof buffer), ==,-1);
  g_assert_cmpint (errno, ==,EPROTO);
  goodix_tls_server_deinit (s,NULL); assert_clean(s); g_free(s);
}
int main (int argc, char **argv)
{
  g_assert_cmpint (argc, ==,2);
  if (!strcmp (argv[1],"real-tls")) real_tls ();
  else if (!strcmp (argv[1],"flight-fragmentation")) flight_fragmentation ();
  else if (!strcmp (argv[1],"partial-init"))
    {
      for (fail_at=1;fail_at<=9;fail_at++)
        {
          boundary=0; GoodixTlsServer *s=make_server(); GError *e=NULL;
          g_assert_false(goodix_tls_server_init(s,&e)); g_assert_nonnull(e); g_clear_error(&e);
          assert_clean(s); g_assert_true(goodix_tls_server_deinit(s,&e)); assert_clean(s); g_free(s);
        }
    }
  else if (!strcmp (argv[1],"silent-timeout"))
    {
      GoodixTlsServer *s=make_server(); GError *e=NULL;
      gint64 start=g_get_monotonic_time(); g_assert_true(goodix_tls_server_init(s,&e));
      while(g_atomic_int_get(&s->accept_result)==0)
        {g_assert_cmpint(g_get_monotonic_time()-start,<,1000000);g_usleep(1000);}
      g_assert_cmpint(g_atomic_int_get(&s->accept_result),==,-1);
      g_assert_error(s->accept_error,G_IO_ERROR,G_IO_ERROR_TIMED_OUT);
      goodix_tls_server_deinit(s,NULL);assert_clean(s);g_free(s);
    }
  else if (!strcmp(argv[1],"stop-join"))
    {
      for(guint i=0;i<100;i++)
        {
          GoodixTlsServer *s=make_server();GError *e=NULL;
          g_assert_true(goodix_tls_server_init(s,&e));
          gint64 start=g_get_monotonic_time();
          g_assert_true(goodix_tls_server_deinit(s,&e));g_assert_no_error(e);
          g_assert_cmpint(g_get_monotonic_time()-start,<,500000);
          assert_clean(s);g_free(s);
        }
    }
  else g_assert_not_reached();
  return 0;
}
