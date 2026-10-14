/* Offline transport/SSM harness. The runner inserts the actual driver types and
 * function bodies at the markers below, preserving their upstream notices.
 * GLib errors, ownership and atomics are real. USB, socket/SSL operations and
 * libfprint scheduling are synthetic; no thread or sensor is started.
 * This does not exercise concurrent teardown, blocking waits or partial init.
 */
#include <gio/gio.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>

typedef struct _SSL SSL;
typedef struct _SSL_CTX SSL_CTX;
typedef struct _FpDevice FpDevice;
typedef FpDevice FpiDeviceGoodixTls;
typedef FpDevice FpImageDevice;
typedef struct _FpiSsm FpiSsm;

#define FPI_DEVICE_GOODIXTLS(dev) ((FpiDeviceGoodixTls *) (dev))
#define FP_DEVICE(dev) ((FpDevice *) (dev))
#define FP_IMAGE_DEVICE(dev) ((FpImageDevice *) (dev))
#define GOODIX_TIMEOUT 1000
#define GOODIX_CMD_MCU_GET_IMAGE 0x20
#define GOODIX_CMD_ACK 0xb0
#define GOODIX_CMD_REQUEST_TLS_CONNECTION 0xd0
#define GOODIX_CMD_TLS_SUCCESSFULLY_ESTABLISHED 0xd4
#define GOODIX_FLAGS_TLS 0xb0
#define fp_dbg(...) ((void) 0)
#define fp_warn(...) ((void) 0)
#define fp_err(...) ((void) 0)
#undef G_DEBUG_HERE
#define G_DEBUG_HERE() ((void) 0)

/* INSERT DRIVER TYPES */

typedef void (*SsmRun) (FpiSsm *, FpDevice *);
typedef void (*SsmDone) (FpiSsm *, FpDevice *, GError *);
typedef void (*TimeoutCallback) (FpDevice *, gpointer);

typedef struct
{
  guint calls, failures, successes;
  GError *error;
  gboolean restart;
} Result;

struct _FpDevice
{
  FpiDeviceGoodixTlsPrivate priv;
  Result tls, image, activation;
  guint requests, confirmations, images, packs, reads, inits, deinits;
  guint local_reads, local_sends;
  guint fail_read_at, fail_send_at, fail_pack_at;
  int read_result, send_result;
  gboolean fail_init;
  GPtrArray *sources;
  guint live_ssms;
};

struct _FpiSsm
{
  FpDevice *dev;
  SsmRun run;
  SsmDone done;
  guint state, states;
  gpointer data;
  gboolean finished;
};

/* Prototypes are needed because inserted functions follow the stand-ins. */
void goodix_reset_state (FpDevice *);
void goodix_receive_done (FpDevice *, guint8 *, guint16, GError *);
void goodix_receive_none (FpDevice *, guint8 *, guint16, gpointer, GError *);
void goodix_receive_default (FpDevice *, guint8 *, guint16, gpointer, GError *);
void goodix_receive_ack (FpDevice *, guint8 *, guint16, gpointer, GError *);
void goodix_receive_protocol (FpDevice *, guint8 *, guint32);
void goodix_send_mcu_get_image (FpDevice *, GoodixImageCallback, gpointer);
void goodix_tls (FpDevice *, GoodixNoneCallback, gpointer);
gboolean goodix_shutdown_tls (FpDevice *, GError **);
static void goodix_reimage_tls_ready (FpDevice *, gpointer, GError *);
static void goodix_tls_finish (FpDevice *, GError *);
static void goodix_tls_poll (FpDevice *, gpointer);
static void on_goodix_tls_server_ready (GoodixTlsServer *, GError *, gpointer);
static void tls_activation_complete (FpDevice *, gpointer, GError *);

static FpiDeviceGoodixTlsPrivate *
fpi_device_goodixtls_get_instance_private (FpiDeviceGoodixTls *dev)
{
  return &dev->priv;
}

static GError *
injected_error (void)
{
  return g_error_new_literal (G_IO_ERROR, G_IO_ERROR_TIMED_OUT,
                              "synthetic transport failure");
}

static void
record_result (Result *result, GError *error)
{
  result->calls++;
  if (error)
    {
      result->failures++;
      g_assert_null (result->error);
      result->error = error;
    }
  else
    result->successes++;
}

static void
tls_result (FpDevice *dev, gpointer user_data, GError *error)
{
  g_assert_true (user_data == &dev->tls);
  record_result (&dev->tls, error);
  if (dev->tls.restart)
    {
      dev->tls.restart = FALSE;
      goodix_shutdown_tls (dev, NULL);
      goodix_tls (dev, tls_result, &dev->tls);
    }
}

static void
image_result (FpDevice *dev, guint8 *data, guint16 length,
              gpointer user_data, GError *error)
{
  g_assert_true (user_data == &dev->image);
  record_result (&dev->image, error);
}

static void
fpi_image_device_activate_complete (FpImageDevice *dev, GError *error)
{
  record_result (&dev->activation, error);
}

/* One-byte command frames are deliberately a fixture format. Framing/checksum
 * parsers are outside this test; receive_protocol's actual dispatch is tested. */
static gboolean
goodix_decode_protocol (guint8 *data, guint32 length, guint8 *cmd,
                        guint8 **payload, guint16 *payload_len,
                        gboolean *valid_checksum, gboolean *valid_null_checksum)
{
  g_assert_cmpuint (length, ==, 1);
  *cmd = data[0];
  *payload = g_malloc0 (1);
  *payload_len = 0;
  *valid_checksum = *valid_null_checksum = TRUE;
  return TRUE;
}

static void
goodix_send_protocol (FpDevice *dev, guint8 cmd, guint8 *payload,
                      guint16 length, GDestroyNotify free_func,
                      gboolean calc_checksum, guint timeout_ms,
                      gboolean reply, GoodixCmdCallback callback,
                      gpointer user_data)
{
  FpiDeviceGoodixTlsPrivate *priv = &dev->priv;
  /* Fail immediately if an SSM overwrites an outstanding callback. */
  g_assert_null (priv->callback);
  g_assert_false (priv->ack || priv->reply);
  priv->cmd = cmd;
  priv->ack = TRUE;
  priv->reply = reply;
  priv->callback = callback;
  priv->user_data = user_data;
  if (cmd == GOODIX_CMD_REQUEST_TLS_CONNECTION)
    dev->requests++;
  else if (cmd == GOODIX_CMD_TLS_SUCCESSFULLY_ESTABLISHED)
    dev->confirmations++;
  else if (cmd == GOODIX_CMD_MCU_GET_IMAGE)
    dev->images++;
  if (free_func)
    free_func (payload);
}

static void
goodix_send_request_tls_connection (FpDevice *dev,
                                    GoodixDefaultCallback callback,
                                    gpointer user_data)
{
  GoodixCallbackInfo *info = g_new0 (GoodixCallbackInfo, 1);
  info->callback = G_CALLBACK (callback);
  info->user_data = user_data;
  goodix_send_protocol (dev, GOODIX_CMD_REQUEST_TLS_CONNECTION, NULL, 0,
                        NULL, TRUE, 0, TRUE, goodix_receive_default, info);
}

static void
goodix_send_tls_successfully_established (FpDevice *dev,
                                         GoodixNoneCallback callback,
                                         gpointer user_data)
{
  GoodixCallbackInfo *info = g_new0 (GoodixCallbackInfo, 1);
  info->callback = G_CALLBACK (callback);
  info->user_data = user_data;
  goodix_send_protocol (dev, GOODIX_CMD_TLS_SUCCESSFULLY_ESTABLISHED, NULL, 0,
                        NULL, TRUE, GOODIX_TIMEOUT, FALSE, goodix_receive_none,
                        info);
}

static void
goodix_receive_data (FpDevice *dev)
{
  dev->reads++;
}

static gboolean
goodix_send_pack (FpDevice *dev, guint8 flags, guint8 *payload, guint16 length,
                  GDestroyNotify free_func, GError **error)
{
  g_assert_cmpuint (flags, ==, GOODIX_FLAGS_TLS);
  g_assert_cmpuint (length, ==, 4);
  dev->packs++;
  if (dev->fail_pack_at == dev->packs)
    {
      *error = injected_error ();
      return FALSE;
    }
  return TRUE;
}

static gboolean
goodix_tls_server_init (GoodixTlsServer *server, GError **error)
{
  FpDevice *dev = server->user_data;
  dev->inits++;
  g_assert_cmpint (server->sock_fd, ==, -1);
  g_assert_cmpint (server->client_fd, ==, -1);
  g_assert_cmpint (g_atomic_int_get (&server->accept_result), ==, 0);
  if (dev->fail_init)
    {
      *error = injected_error ();
      return FALSE;
    }
  return TRUE;
}

static gboolean
goodix_tls_server_deinit (GoodixTlsServer *server, GError **error)
{
  FpDevice *dev = server->user_data;
  dev->deinits++;
  g_clear_error (&server->accept_error);
  return TRUE;
}

static int
goodix_tls_client_recv (GoodixTlsServer *server, guint8 *data, guint16 length)
{
  FpDevice *dev = server->user_data;
  dev->local_reads++;
  if (dev->local_reads == dev->fail_read_at)
    return dev->read_result;
  g_assert_cmpuint (length, >=, 4);
  memset (data, 0x42, 4);
  return 4;
}

static int
goodix_tls_client_send (GoodixTlsServer *server, guint8 *data, guint16 length)
{
  FpDevice *dev = server->user_data;
  dev->local_sends++;
  return dev->local_sends == dev->fail_send_at ? dev->send_result : length;
}

static GSource *
fpi_device_add_timeout (FpDevice *dev, guint interval, TimeoutCallback callback,
                        gpointer user_data, GDestroyNotify destroy)
{
  /* Keep the owner reference as the real libfprint main context would. */
  GSource *source = g_timeout_source_new (interval);
  g_assert_true (callback == goodix_tls_poll);
  g_ptr_array_add (dev->sources, source);
  return source;
}

static FpiSsm *
fpi_ssm_new (FpDevice *dev, SsmRun run, guint states)
{
  FpiSsm *ssm = g_new0 (FpiSsm, 1);
  ssm->dev = dev;
  ssm->run = run;
  ssm->states = states;
  dev->live_ssms++;
  return ssm;
}

static void
fpi_ssm_start (FpiSsm *ssm, SsmDone done)
{
  ssm->done = done;
  ssm->run (ssm, ssm->dev);
}

static guint
fpi_ssm_get_cur_state (FpiSsm *ssm)
{
  g_assert_false (ssm->finished);
  return ssm->state;
}

static gpointer
fpi_ssm_get_data (FpiSsm *ssm)
{
  return ssm->data;
}

static void
fpi_ssm_set_data (FpiSsm *ssm, gpointer data, GDestroyNotify destroy)
{
  g_assert_null (destroy);
  ssm->data = data;
}

static void
ssm_finish (FpiSsm *ssm, GError *error)
{
  g_assert_false (ssm->finished);
  ssm->finished = TRUE;
  ssm->dev->live_ssms--;
  ssm->done (ssm, ssm->dev, error);
  g_free (ssm);
}

static void
fpi_ssm_mark_failed (FpiSsm *ssm, GError *error)
{
  g_assert_nonnull (error);
  ssm_finish (ssm, error);
}

static void
fpi_ssm_next_state (FpiSsm *ssm)
{
  g_assert_false (ssm->finished);
  if (++ssm->state == ssm->states)
    ssm_finish (ssm, NULL);
  else
    ssm->run (ssm, ssm->dev);
}

/* INSERT DRIVER FUNCTIONS */

static void
respond (FpDevice *dev, GError *error)
{
  guint8 data[4] = {0x42, 0x42, 0x42, 0x42};
  g_assert_true (dev->priv.ack || dev->priv.reply);
  goodix_receive_done (dev, data, sizeof (data), error);
}

static void
publish (FpDevice *dev, GError *error)
{
  GoodixTlsServer *server = dev->priv.tls_hop;
  g_assert_nonnull (server);
  g_assert_cmpint (g_atomic_int_get (&server->accept_result), ==, 0);
  server->connection_callback (server, error, server->user_data);
  g_assert_cmpint (g_atomic_int_get (&server->accept_result), ==,
                   error ? -1 : 1);
}

static void
poll_once (FpDevice *dev)
{
  g_assert_nonnull (dev->priv.tls_poll);
  g_source_destroy (dev->priv.tls_poll);
  goodix_tls_poll (dev, NULL);
}

static void
start_tls (FpDevice *dev)
{
  goodix_tls (dev, tls_result, &dev->tls);
  if (!dev->fail_init)
    {
      g_assert_cmpuint (dev->priv.cmd, ==, GOODIX_CMD_REQUEST_TLS_CONNECTION);
      g_assert_nonnull (dev->priv.tls_ready_callback);
    }
}

static void
drive_proxy (FpDevice *dev)
{
  /* Request reply, then three client flights. Server flights are canned reads. */
  for (guint i = 0; i < 4; i++)
    {
      g_assert_nonnull (dev->priv.tls_ready_callback);
      respond (dev, NULL);
    }
}

static void
finish_success (FpDevice *dev)
{
  drive_proxy (dev);
  g_assert_nonnull (dev->priv.tls_ssm);
  g_assert_cmpuint (fpi_ssm_get_cur_state (dev->priv.tls_ssm), ==,
                    TLS_HANDSHAKE_STAGE_WAIT_ACCEPT);
  publish (dev, NULL);
  poll_once (dev);
  g_assert_null (dev->priv.tls_ssm);
  g_assert_cmpuint (dev->priv.cmd, ==, GOODIX_CMD_TLS_SUCCESSFULLY_ESTABLISHED);
  respond (dev, NULL);
}

static void
expect_tls_error (FpDevice *dev, gboolean injected)
{
  g_assert_cmpuint (dev->tls.calls, ==, 1);
  g_assert_cmpuint (dev->tls.failures, ==, 1);
  g_assert_cmpuint (dev->tls.successes, ==, 0);
  g_assert_nonnull (dev->tls.error);
  if (injected)
    g_assert_true (g_error_matches (dev->tls.error, G_IO_ERROR,
                                    G_IO_ERROR_TIMED_OUT));
  g_assert_null (dev->priv.tls_ready_callback);
  g_assert_null (dev->priv.tls_poll);
  g_assert_null (dev->priv.tls_ssm);
  g_assert_null (dev->priv.callback);
  g_assert_false (dev->priv.ack || dev->priv.reply);
  g_assert_cmpuint (dev->live_ssms, ==, 0);
}

static void
restart_reply (FpDevice *dev)
{
  guint8 command = GOODIX_CMD_REQUEST_TLS_CONNECTION;
  goodix_receive_protocol (dev, &command, 1);
}

static void
case_retry_budget (FpDevice *dev)
{
  goodix_send_mcu_get_image (dev, image_result, &dev->image);
  for (guint i = 1; i <= 2; i++)
    {
      restart_reply (dev);
      g_assert_cmpuint (dev->priv.reimage_tries, ==, i);
      finish_success (dev);
      g_assert_cmpuint (dev->priv.reimage_tries, ==, i);
      g_assert_cmpuint (dev->priv.cmd, ==, GOODIX_CMD_MCU_GET_IMAGE);
      g_assert_cmpuint (dev->image.calls, ==, 0);
    }
  restart_reply (dev);
  g_assert_cmpuint (dev->inits, ==, 2);
  g_assert_cmpuint (dev->requests, ==, 2);
  g_assert_cmpuint (dev->confirmations, ==, 2);
  g_assert_cmpuint (dev->images, ==, 3);
  g_assert_cmpuint (dev->image.calls, ==, 1);
  g_assert_cmpuint (dev->image.failures, ==, 1);
  g_assert_cmpuint (dev->priv.reimage_tries, ==, 0);
  g_assert_null (dev->priv.reimage_callback);
  g_clear_error (&dev->image.error);
  goodix_send_mcu_get_image (dev, image_result, &dev->image);
  restart_reply (dev);
  g_assert_cmpuint (dev->priv.reimage_tries, ==, 1);
  finish_success (dev);
  respond (dev, NULL);
  g_assert_cmpuint (dev->image.calls, ==, 2);
  g_assert_cmpuint (dev->image.successes, ==, 1);
  g_assert_cmpuint (dev->priv.reimage_tries, ==, 0);
}

static void
cleanup (FpDevice *dev)
{
  g_assert_cmpuint (dev->live_ssms, ==, 0);
  g_assert_null (dev->priv.callback);
  g_assert_null (dev->priv.reimage_callback);
  g_assert_null (dev->priv.tls_ready_callback);
  goodix_shutdown_tls (dev, NULL);
  g_clear_error (&dev->tls.error);
  g_clear_error (&dev->image.error);
  g_clear_error (&dev->activation.error);
  for (guint i = 0; i < dev->sources->len; i++)
    g_source_destroy (g_ptr_array_index (dev->sources, i));
  g_ptr_array_unref (dev->sources);
}

int
main (int argc, char **argv)
{
  g_assert_cmpint (argc, ==, 2);
  const char *name = argv[1];
  FpDevice dev = {0};
  dev.sources = g_ptr_array_new_with_free_func ((GDestroyNotify) g_source_unref);

  if (!strcmp (name, "retry-budget"))
    case_retry_budget (&dev);
  else if (!strcmp (name, "command-budget"))
    {
      dev.priv.reimage_tries = 2;
      goodix_send_protocol (&dev, 0xa8, NULL, 0, NULL, TRUE, 1, TRUE, NULL, NULL);
      respond (&dev, NULL);
      g_assert_cmpuint (dev.priv.reimage_tries, ==, 2);
      start_tls (&dev);
      finish_success (&dev);
      g_assert_cmpuint (dev.priv.reimage_tries, ==, 2);
    }
  else if (!strcmp (name, "terminal-reset") || !strcmp (name, "new-image-reset"))
    {
      dev.priv.reimage_tries = 2;
      goodix_send_mcu_get_image (&dev, image_result, &dev.image);
      g_assert_cmpuint (dev.priv.reimage_tries, ==, 0);
      dev.priv.reimage_tries = 2;
      respond (&dev, !strcmp (name, "terminal-reset") ? injected_error () : NULL);
      g_assert_cmpuint (dev.priv.reimage_tries, ==, 0);
      g_assert_cmpuint (dev.image.calls, ==, 1);
    }
  else if (!strcmp (name, "activation-error"))
    {
      goodix_tls (&dev, tls_activation_complete, NULL);
      respond (&dev, injected_error ());
      g_assert_cmpuint (dev.activation.calls, ==, 1);
      g_assert_cmpuint (dev.activation.failures, ==, 1);
      g_assert_true (g_error_matches (dev.activation.error, G_IO_ERROR,
                                      G_IO_ERROR_TIMED_OUT));
    }
  else if (!strcmp (name, "init-error"))
    {
      dev.fail_init = TRUE;
      start_tls (&dev);
      expect_tls_error (&dev, TRUE);
      g_assert_cmpuint (dev.requests, ==, 0);
      g_assert_cmpuint (dev.deinits, ==, 1);
      g_assert_null (dev.priv.tls_hop);
    }
  else if (!strcmp (name, "reentrant-finish"))
    {
      start_tls (&dev);
      dev.tls.restart = TRUE;
      respond (&dev, injected_error ());
      g_assert_cmpuint (dev.tls.calls, ==, 1);
      g_assert_cmpuint (dev.requests, ==, 2);
      g_assert_nonnull (dev.priv.tls_ready_callback);
      g_assert_nonnull (dev.priv.tls_poll);
      g_assert_nonnull (dev.priv.callback);
      finish_success (&dev);
      g_assert_cmpuint (dev.tls.calls, ==, 2);
      g_assert_cmpuint (dev.tls.successes, ==, 1);
    }
  else if (!strcmp (name, "duplicate-finish"))
    {
      start_tls (&dev);
      respond (&dev, injected_error ());
      expect_tls_error (&dev, TRUE);
      goodix_tls_finish (&dev, injected_error ());
      goodix_tls_finish (&dev, NULL);
      expect_tls_error (&dev, TRUE);
      /* LeakSanitizer verifies ownership of the unused secondary GError. */
    }
  else
    {
      if (!strcmp (name, "hello-eof") || !strcmp (name, "final-eof"))
        dev.fail_read_at = !strcmp (name, "hello-eof") ? 1 : 2;
      if (!strcmp (name, "initial-short-send") || !strcmp (name, "initial-negative-send") ||
          !strcmp (name, "proxy-short-send") || !strcmp (name, "proxy-negative-send"))
        {
          dev.fail_send_at = g_str_has_prefix (name, "initial") ? 1 : 2;
          dev.send_result = strstr (name, "negative") ? -1 : 2;
        }
      if (!strcmp (name, "initial-pack-error") || !strcmp (name, "final-pack-error"))
        dev.fail_pack_at = !strcmp (name, "initial-pack-error") ? 1 : 2;
      start_tls (&dev);
      if (!strcmp (name, "request-error"))
        respond (&dev, injected_error ());
      else if (!strcmp (name, "proxy-error"))
        {
          respond (&dev, NULL);
          respond (&dev, injected_error ());
        }
      else if (dev.fail_send_at || dev.fail_read_at || dev.fail_pack_at)
        {
          while (dev.priv.tls_ready_callback)
            respond (&dev, NULL);
        }
      else if (!strcmp (name, "worker-failure-wait") || !strcmp (name, "worker-error-fallback"))
        {
          respond (&dev, NULL);
          g_assert_nonnull (dev.priv.tls_ssm);
          g_assert_true (dev.priv.reply);
          publish (&dev, injected_error ());
          if (!strcmp (name, "worker-error-fallback"))
            g_clear_error (&dev.priv.tls_hop->accept_error);
          g_assert_cmpuint (dev.tls.calls, ==, 0);
          poll_once (&dev);
          expect_tls_error (&dev, !strcmp (name, "worker-failure-wait"));
        }
      else if (!strcmp (name, "worker-success-proxy"))
        {
          respond (&dev, NULL);
          publish (&dev, NULL);
          poll_once (&dev);
          g_assert_cmpuint (dev.confirmations, ==, 0);
          g_assert_cmpuint (dev.tls.calls, ==, 0);
          g_assert_nonnull (dev.priv.tls_ssm);
          for (guint i = 0; i < 3; i++)
            respond (&dev, NULL);
          g_assert_cmpuint (dev.confirmations, ==, 1);
          g_assert_cmpuint (dev.tls.calls, ==, 0);
          respond (&dev, NULL);
        }
      else if (!strcmp (name, "worker-pending") || !strcmp (name, "confirmation-error"))
        {
          drive_proxy (&dev);
          g_assert_cmpuint (dev.confirmations, ==, 0);
          g_assert_cmpuint (dev.tls.calls, ==, 0);
          g_assert_cmpuint (fpi_ssm_get_cur_state (dev.priv.tls_ssm), ==,
                            TLS_HANDSHAKE_STAGE_WAIT_ACCEPT);
          if (!strcmp (name, "worker-pending"))
            {
              poll_once (&dev);
              poll_once (&dev);
              g_assert_cmpuint (dev.confirmations, ==, 0);
              g_assert_cmpuint (dev.tls.calls, ==, 0);
            }
          publish (&dev, NULL);
          poll_once (&dev);
          g_assert_cmpuint (dev.confirmations, ==, 1);
          g_assert_cmpuint (dev.tls.calls, ==, 0);
          respond (&dev, !strcmp (name, "confirmation-error") ? injected_error () : NULL);
        }
      else
        {
          g_assert_cmpstr (name, ==, "success");
          finish_success (&dev);
        }

      if (!strcmp (name, "success") || !strcmp (name, "worker-pending") ||
          !strcmp (name, "worker-success-proxy"))
        {
          g_assert_cmpuint (dev.tls.calls, ==, 1);
          g_assert_cmpuint (dev.tls.successes, ==, 1);
          g_assert_cmpuint (dev.tls.failures, ==, 0);
          g_assert_cmpuint (dev.confirmations, ==, 1);
          g_assert_null (dev.priv.tls_ready_callback);
          g_assert_null (dev.priv.tls_poll);
        }
      else
        {
          gboolean propagated = !strcmp (name, "request-error") ||
            !strcmp (name, "proxy-error") || !strcmp (name, "confirmation-error") ||
            dev.fail_pack_at || !strcmp (name, "worker-failure-wait");
          expect_tls_error (&dev, propagated);
          g_assert_cmpuint (dev.confirmations, ==,
                            !strcmp (name, "confirmation-error") ? 1 : 0);
        }
    }
  cleanup (&dev);
  return 0;
}
