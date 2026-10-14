/* Synthetic dependency boundary for actual LGPL-2.1+ Goodix 55x4 functions.
 * No USB, device objects, TLS session or biometric inputs are constructed. */
#include <gio/gio.h>
#include <stdarg.h>
#include <string.h>
#include <stdio.h>

typedef struct _FakeDevice FpDevice;
typedef struct _FakeSsm FpiSsm;
typedef void (*SsmDone)(FpiSsm *, FpDevice *, GError *);
struct _FakeSsm { guint steps, failures, completions; GError *error; SsmDone callback; FpDevice *dev; };
struct _FakeDevice { guint opens, closes, session_errors, deactivations, led;
                 GError *error; guint led_state; gboolean fdt_thresholds_valid; guint8 fdt_thresholds[12];
                 gboolean empty_img_valid, cal_have_prev;
                 guint cal_attempts;
                 guint16 cal_prev[108 * 88], empty_img[108 * 88];
                 FpiSsm *scan_ssm, *calibration_ssm; GSource *scan_retry;
                 gboolean deactivating, led_want_on; };
typedef FpDevice FpImageDevice;
typedef FpDevice FpiDeviceGoodixTls55X4;
#define FP_DEVICE(x) (x)
#define FP_IMAGE_DEVICE(x) (x)
#define FPI_DEVICE_GOODIXTLS55X4(x) (x)
#define SLEEP_STAGE_SWITCH_TO_SLEEP_MODE 0
#define SLEEP_STAGE_SWITCH_TO_SLEEP_MODE_REALTEK 1
#define SLEEP_STAGE_DEACTIVATE 2
#define SCAN_EMPTY_GET_IMG 2
#define GOODIX55X4_CAL_STABLE_DIFF 12.0
#define GOODIX55X4_CAL_MAX_ATTEMPTS 16
#define GOODIX55X4_CAL_RETRY_DELAY_MS 150
#define GOODIX55X4_LED_UNKNOWN 0
#define GOODIX55X4_LED_OFF 1
#define GOODIX55X4_LED_ON 2
#define GOODIX_CMD_QUERY_MCU_STATE 0xae
#define GOODIX_TIMEOUT 1000
#define GOODIX55X4_FDT_REPLY_HDR 4
#define GOODIX55X4_FDT_ZONES 12
#define GOODIX_55X4_FLAG_LEARN_FDT 1
#define GOODIX_55X4_PSK_FLAGS 0xbb020007
#define GOODIX55X4_WIDTH 108
#define GOODIX55X4_SCAN_WIDTH 108
#define GOODIX55X4_HEIGHT 88
#define GOODIX55X4_FRAME_SIZE (108 * 88)
#define GOODIX55X4_RAW_FRAME_SIZE (108 * 88 / 4 * 6)
typedef unsigned short Goodix55X4Pix;
/* INSERT EXPECTED HASH */
static gboolean claim_ok, release_ok;
static guint releases, shutdowns, resets, calibration_timers;
static GString *diagnostics;
static void record(const gchar *format, ...) {
  va_list args; va_start(args, format);
  g_string_append_vprintf(diagnostics, format, args);
  va_end(args);
}
#define fp_dbg record
#define fp_err record
#define fp_warn record
static guint64 fpi_device_get_driver_data(FpDevice *dev) { return 1; }
static void goodix55x4_clear_led(FpDevice *dev) { dev->led++; }
static void fpi_ssm_mark_failed(FpiSsm *ssm, GError *error) {
  ssm->failures++;
  if (ssm->callback)
    ssm->callback(ssm, ssm->dev, error);
  else
    ssm->error = error;
}
static void fpi_ssm_next_state(FpiSsm *ssm) { ssm->steps++; }
static guint fpi_ssm_get_cur_state(FpiSsm *ssm) { return SLEEP_STAGE_DEACTIVATE; }
static void fpi_ssm_mark_completed(FpiSsm *ssm) { ssm->completions++; }
static void check_idle(FpDevice *dev, gpointer data, GError *error) { }
static void check_sleep_realtek(FpDevice *dev, gboolean success, gpointer data, GError *error) { }
static void goodix_send_mcu_switch_to_sleep_mode(FpDevice *dev, guint delay,
    void (*callback)(FpDevice *, gpointer, GError *), gpointer data) { }
static void goodix_send_mcu_switch_to_sleep_mode_realtek(FpDevice *dev, guint mode,
    void (*callback)(FpDevice *, gboolean, gpointer, GError *), gpointer data) { }
static void fpi_ssm_jump_to_state(FpiSsm *ssm, guint state) { ssm->steps++; }
static GSource *fpi_device_add_timeout(FpDevice *dev, guint interval,
                                      void (*callback)(FpDevice *, gpointer),
                                      gpointer data, GDestroyNotify destroy) {
  g_assert_cmpuint(interval, ==, GOODIX55X4_CAL_RETRY_DELAY_MS);
  calibration_timers++;
  return NULL;
}
static gboolean goodix_dev_init(FpDevice *dev, GError **error) {
  if (!claim_ok) g_set_error_literal(error, G_IO_ERROR, G_IO_ERROR_PERMISSION_DENIED,
                                    "synthetic claim failure");
  return claim_ok;
}
static gboolean goodix_dev_deinit(FpDevice *dev, GError **error) {
  releases++;
  if (!release_ok) g_set_error_literal(error, G_IO_ERROR, G_IO_ERROR_FAILED,
                                      "synthetic release failure");
  return release_ok;
}
static void goodix_reset_state(FpDevice *dev) { resets++; }
typedef void (*CmdCallback)(FpDevice *, guint8 *, guint16, gpointer, GError *);
static CmdCallback pending_close;
static void goodix_send_protocol(FpDevice *dev, guint8 command, guint8 *payload,
                                 guint16 length, GDestroyNotify free_func,
                                 gboolean ack, guint timeout, gboolean reply,
                                 CmdCallback callback, gpointer user_data) {
  g_assert_cmpuint(command, ==, 0xae); g_assert_cmpuint(length, ==, 3);
  g_assert_cmpuint(payload[0], ==, 1); g_assert_cmpuint(payload[1], ==, 0);
  g_assert_cmpuint(payload[2], ==, 0x32); g_assert_cmpuint(timeout, >, 0);
  g_assert_true(ack); g_assert_true(reply);
  dev->led++; pending_close = callback;
}
static void fpi_image_device_open_complete(FpImageDevice *dev, GError *error) {
  dev->opens++; dev->error = error;
}
static void fpi_image_device_close_complete(FpImageDevice *dev, GError *error) {
  dev->closes++; dev->error = error;
}
static void fpi_image_device_session_error(FpImageDevice *dev, GError *error) {
  dev->session_errors++; dev->error = error;
}
static void fpi_image_device_deactivate_complete(FpImageDevice *dev, GError *error) {
  dev->deactivations++; dev->error = error;
}
static gboolean goodix_shutdown_tls(FpDevice *dev, GError **error) {
  shutdowns++;
  g_set_error_literal(error, G_IO_ERROR, G_IO_ERROR_FAILED, "synthetic shutdown failure");
  return FALSE;
}
static void goodix55X4_reset_state(FpiDeviceGoodixTls55X4 *dev) { resets++; }
static guint abort_calls, sleep_starts;
static gboolean abort_has_command;
static void goodix_abort_operation(FpDevice *dev) {
  abort_calls++;
  if (abort_has_command) {
    FpiSsm *ssm = dev->calibration_ssm ? dev->calibration_ssm : dev->scan_ssm;
    fpi_ssm_mark_failed(ssm, g_error_new_literal(
      G_IO_ERROR, G_IO_ERROR_CANCELLED, "synthetic pending command cancelled"));
  }
}
static void sleep_start(FpDevice *dev, gpointer user_data) {
  g_assert_null(dev->scan_ssm); g_assert_null(dev->calibration_ssm);
  g_assert_null(dev->scan_retry); g_assert_true(dev->deactivating);
  sleep_starts++;
}
/* INSERT DRIVER FUNCTIONS */

int main(void) {
  diagnostics = g_string_new(NULL);
  FpDevice dev = {0}; FpiSsm ssm = {0};
  claim_ok = FALSE; dev_init(&dev);
  g_assert_cmpuint(dev.opens, ==, 1); g_assert_nonnull(dev.error);
  g_assert_cmpuint(dev.led, ==, 0); g_clear_error(&dev.error);
  claim_ok = TRUE; dev_init(&dev);
  g_assert_cmpuint(dev.opens, ==, 2); g_assert_null(dev.error);
  release_ok = FALSE; dev_deinit(&dev);
  g_assert_cmpuint(releases, ==, 0); g_assert_cmpuint(dev.closes, ==, 0);
  pending_close(&dev, NULL, 0, NULL, NULL);
  g_assert_cmpuint(dev.closes, ==, 1); g_assert_nonnull(dev.error);
  g_assert_cmpuint(releases, ==, 1); g_clear_error(&dev.error);
  release_ok = TRUE; dev_deinit(&dev);
  g_assert_cmpuint(releases, ==, 1); g_assert_cmpuint(dev.closes, ==, 1);
  pending_close(&dev, NULL, 0, NULL, NULL);
  g_assert_cmpuint(dev.closes, ==, 2); g_assert_null(dev.error);
  g_assert_cmpuint(releases, ==, 2);
  release_ok = FALSE; dev_deinit(&dev);
  GError *led_error = g_error_new_literal(G_IO_ERROR, G_IO_ERROR_TIMED_OUT, "synthetic LED timeout");
  pending_close(&dev, NULL, 0, NULL, led_error);
  g_assert_true(dev.error == led_error); g_assert_cmpuint(releases, ==, 3);
  g_clear_error(&dev.error);

  guint8 sentinel[32]; memset(sentinel, 0xa7, sizeof sentinel);
  check_preset_psk_read(&dev, TRUE, GOODIX_55X4_PSK_FLAGS, sentinel, 32, &ssm, NULL);
  g_assert_cmpuint(ssm.failures, ==, 1);
  g_assert_null(strstr(ssm.error->message, "a7"));
  g_assert_null(strstr(diagnostics->str, "a7")); g_clear_error(&ssm.error);
  check_preset_psk_read(&dev, TRUE, GOODIX_55X4_PSK_FLAGS, sentinel, 31, &ssm, NULL);
  g_assert_cmpuint(ssm.failures, ==, 2);
  g_assert_null(strstr(ssm.error->message, "a7")); g_clear_error(&ssm.error);
  check_preset_psk_read(&dev, TRUE, GOODIX_55X4_PSK_FLAGS, NULL, 32, &ssm, NULL);
  g_assert_cmpuint(ssm.failures, ==, 3); g_clear_error(&ssm.error);
  check_preset_psk_read(&dev, TRUE, GOODIX_55X4_PSK_FLAGS,
                        (guint8 *)goodix_55x4_psk_0, 32, &ssm, NULL);
  g_assert_cmpuint(ssm.steps, ==, 1);
  check_firmware_version(&dev, "GF3268_RTSEC_APP_10062", &ssm, NULL);
  g_assert_cmpuint(ssm.steps, ==, 2);
  check_firmware_version(&dev, "GF3268_RTSEC_APP_10063", &ssm, NULL);
  g_assert_cmpuint(ssm.failures, ==, 4); g_clear_error(&ssm.error);
  check_firmware_version(&dev, NULL, &ssm, NULL);
  g_assert_cmpuint(ssm.failures, ==, 5); g_clear_error(&ssm.error);

  guint8 baseline[28] = {0};
  for (guint i = 4; i < 28; i += 2) { baseline[i] = 0x9a; baseline[i+1] = 1; }
  guint prior_failures = ssm.failures;
  for (guint length = 0; length < 28; length++) {
    check_fdt_baseline(&dev, baseline, length, &ssm, NULL);
    g_assert_cmpuint(ssm.failures, ==, ++prior_failures);
    g_assert_false(dev.fdt_thresholds_valid); g_clear_error(&ssm.error);
  }
  check_fdt_baseline(&dev, NULL, 28, &ssm, NULL);
  g_assert_cmpuint(ssm.failures, ==, ++prior_failures); g_clear_error(&ssm.error);
  check_fdt_baseline(&dev, baseline, 28, &ssm, NULL);
  g_assert_true(dev.fdt_thresholds_valid);
  for (guint i = 0; i < 12; i++) g_assert_cmpuint(dev.fdt_thresholds[i], ==, 205);
  g_assert_null(strstr(diagnostics->str, "cd"));

  Goodix55X4Pix output[GOODIX55X4_FRAME_SIZE];
  memset(output, 0xcc, sizeof output);
  guint8 *raw = g_malloc0(GOODIX55X4_RAW_FRAME_SIZE + 4);
  g_assert_false(decode_frame(output, NULL, GOODIX55X4_RAW_FRAME_SIZE + 4));
  for (guint length = 0; length < GOODIX55X4_RAW_FRAME_SIZE + 4; length++)
    g_assert_false(decode_frame(output, raw, length));
  g_assert_cmpuint(output[0], ==, 0xcccc);
  g_assert_false(decode_frame(output, raw, GOODIX55X4_RAW_FRAME_SIZE + 5));
  for (guint i = 0; i < GOODIX55X4_RAW_FRAME_SIZE; i += 6) {
    raw[i] = 0xab; raw[i+1] = 0xcd; raw[i+2] = 0xef;
    raw[i+3] = 0x12; raw[i+4] = 0x34; raw[i+5] = 0x56;
  }
  g_assert_true(decode_frame(output, raw, GOODIX55X4_RAW_FRAME_SIZE + 4));
  for (guint i = 0; i < GOODIX55X4_FRAME_SIZE; i += 4) {
    g_assert_cmpuint(output[i], ==, 0xbcd);
    g_assert_cmpuint(output[i+1], ==, 0x12a);
    g_assert_cmpuint(output[i+2], ==, 0x6ef);
    g_assert_cmpuint(output[i+3], ==, 0x345);
  }
  /* Sixteen alternating synthetic plate values must fail, schedule only
   * fifteen retries, and never advance to finger scanning/capture. */
  FpDevice cal_dev = {0}; FpiSsm calibration = {0};
  calibration_timers = 0;
  for (guint attempt = 0; attempt < 16; attempt++) {
    memset(raw, attempt % 2 ? 0xff : 0, GOODIX55X4_RAW_FRAME_SIZE + 4);
    on_scan_empty_img(&cal_dev, raw, GOODIX55X4_RAW_FRAME_SIZE + 4, &calibration, NULL);
  }
  g_assert_cmpuint(calibration.failures, ==, 1);
  g_assert_cmpuint(calibration.steps, ==, 0);
  g_assert_cmpuint(calibration_timers, ==, 15);
  g_assert_false(cal_dev.empty_img_valid);
  g_assert_false(cal_dev.cal_have_prev);
  g_assert_cmpuint(cal_dev.cal_attempts, ==, 0);
  g_clear_error(&calibration.error);
  /* A subsequent fresh stable pair is permitted, with one completed baseline. */
  memset(raw, 0, GOODIX55X4_RAW_FRAME_SIZE + 4);
  on_scan_empty_img(&cal_dev, raw, GOODIX55X4_RAW_FRAME_SIZE + 4, &calibration, NULL);
  on_scan_empty_img(&cal_dev, raw, GOODIX55X4_RAW_FRAME_SIZE + 4, &calibration, NULL);
  g_assert_cmpuint(calibration.steps, ==, 1);
  g_assert_true(cal_dev.empty_img_valid);
  g_free(raw);
  FpiSsm led_ssm = {0};
  GError *led_fail = g_error_new_literal(G_IO_ERROR, G_IO_ERROR_FAILED, "synthetic LED failure");
  goodix55x4_led_done(&dev, NULL, 0, &led_ssm, led_fail);
  g_assert_cmpuint(led_ssm.failures, ==, 1);
  g_assert_cmpuint(led_ssm.steps, ==, 0); g_clear_error(&led_ssm.error);
  dev.led_want_on = TRUE;
  goodix55x4_led_done(&dev, NULL, 0, &led_ssm, NULL);
  g_assert_cmpuint(led_ssm.steps, ==, 1); g_assert_cmpuint(dev.led_state, ==, GOODIX55X4_LED_ON);

  /* Exercise deactivation at a command and at both kinds of timer-only wait.
   * SSM callbacks use actual scan_complete/scan_empty_complete functions. */
  for (guint mode = 0; mode < 3; mode++) {
    FpDevice cancelled = {0};
    FpiSsm parent = {.callback = scan_complete, .dev = &cancelled};
    FpiSsm child = {.callback = scan_empty_complete, .dev = &cancelled};
    cancelled.scan_ssm = &parent;
    if (mode != 2) cancelled.calibration_ssm = &child;
    GSource *timer = g_timeout_source_new(10000);
    cancelled.scan_retry = timer;
    abort_has_command = mode == 0;
    guint previous_sleep = sleep_starts;
    dev_deactivate(&cancelled);
    g_assert_cmpuint(parent.failures, ==, 1);
    g_assert_cmpuint(cancelled.session_errors, ==, 0);
    g_assert_cmpuint(sleep_starts, ==, previous_sleep + 1);
    g_assert_true(g_source_is_destroyed(timer));
    g_source_unref(timer);
  }
  g_assert_cmpuint(abort_calls, ==, 3);
  GError *original = g_error_new_literal(G_IO_ERROR, G_IO_ERROR_TIMED_OUT, "synthetic scan timeout");
  scan_complete(&ssm, &dev, original);
  g_assert_cmpuint(dev.session_errors, ==, 1); g_assert_true(dev.error == original);
  g_clear_error(&dev.error);
  original = g_error_new_literal(G_IO_ERROR, G_IO_ERROR_TIMED_OUT, "synthetic sleep timeout");
  sleep_complete(&ssm, &dev, original);
  g_assert_cmpuint(dev.deactivations, ==, 1); g_assert_true(dev.error == original);
  g_assert_cmpuint(shutdowns, ==, 1); g_clear_error(&dev.error);
  FpDevice sleeping = {0}; FpiSsm sleep_ssm = {0};
  sleep_run_state(&sleep_ssm, &sleeping);
  g_assert_cmpuint(sleep_ssm.completions, ==, 1);
  g_assert_cmpuint(sleeping.deactivations, ==, 1);
  g_clear_error(&sleeping.error);
  g_string_free(diagnostics, TRUE);
  puts("PASS: actual claim/release propagation, key privacy, exact firmware, frame lengths/pixels, exhausted/stable calibration, session/deactivation failure completion");
  return 0;
}
