/* SPDX-License-Identifier: MIT
 * Original standalone host-template experiment; linked libfprint is LGPL-2.1+.
 * Reuses this project's reviewed USB descriptor guard and output suppression.
 */
#define main reviewed_capture_main
#include "capture-one.c"
#undef main
#include "fp-print.h"

#define MAX_TEMPLATE (4u * 1024u * 1024u)
#define REVIEWED_SIGFM_TYPE 3

typedef struct {
  GMainLoop *loop;
  GCancellable *cancel;
  FpDevice *device;
  FpPrint *template, *enrolled;
  guint timer, grace, overall, signal_int, signal_term;
  int report_fd, directory_fd;
  uid_t owner; gid_t group;
  gboolean enroll, failed, abandoned, closing, lift_prompted, seen_present, touch_prompted;
  gboolean timed_out, interrupted, retry, decision, decision_match, verified;
  guint progress, retries, decisions;
  const char *stage;
} Recognition;

static gboolean
valid_template (FpPrint *print)
{
  gint type = 0;
  if (!print) return FALSE;
  g_object_get (print, "fpi-type", &type, NULL);
  return type == REVIEWED_SIGFM_TYPE && !fp_print_get_device_stored (print) &&
         g_strcmp0 (fp_print_get_driver (print), "goodixtls55x4") == 0 &&
         fp_print_get_finger (print) == FP_FINGER_RIGHT_INDEX;
}

static FpPrint *
read_template (int fd)
{
  struct stat info;
  if (fstat (fd, &info) != 0 || !S_ISREG (info.st_mode) || info.st_size <= 3 ||
      info.st_size > MAX_TEMPLATE) return NULL;
  int seals = fcntl (fd, F_GET_SEALS);
  if (seals < 0 || (seals & (F_SEAL_WRITE | F_SEAL_GROW | F_SEAL_SHRINK | F_SEAL_SEAL)) !=
                  (F_SEAL_WRITE | F_SEAL_GROW | F_SEAL_SHRINK | F_SEAL_SEAL)) return NULL;
  g_autofree guchar *bytes = g_malloc ((gsize) info.st_size);
  gsize done = 0;
  while (done < (gsize) info.st_size) {
    ssize_t got = pread (fd, bytes + done, (size_t) info.st_size - done, (off_t) done);
    if (got < 0 && errno == EINTR) continue;
    if (got <= 0) return NULL;
    done += got;
  }
  g_autoptr(GError) error = NULL;
  FpPrint *print = fp_print_deserialize (bytes, done, &error);
  if (!valid_template (print)) { g_clear_object (&print); return NULL; }
  return print;
}

static gboolean
save_template (Recognition *trial)
{
  g_autofree guchar *bytes = NULL;
  gsize length = 0;
  g_autoptr(GError) error = NULL;
  if (!valid_template (trial->enrolled) ||
      !fp_print_serialize (trial->enrolled, &bytes, &length, &error) ||
      length <= 3 || length > MAX_TEMPLATE) return FALSE;
  g_autoptr(FpPrint) roundtrip = fp_print_deserialize (bytes, length, &error);
  if (!valid_template (roundtrip) || !fp_print_compatible (roundtrip, trial->device)) return FALSE;
  int fd = openat (trial->directory_fd, "template.bin", O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
  if (fd < 0) return FALSE;
  gboolean ok = fchmod (fd, 0600) == 0 && fchown (fd, trial->owner, trial->group) == 0 &&
                write_all (fd, bytes, length) && fsync (fd) == 0;
  if (close (fd) != 0) ok = FALSE;
  if (!ok) unlinkat (trial->directory_fd, "template.bin", 0);
  return ok;
}

static void recognition_close (Recognition *trial);

static void
recognition_stop_timer (Recognition *trial)
{
  if (trial->timer) { g_source_remove (trial->timer); trial->timer = 0; }
  if (trial->grace) { g_source_remove (trial->grace); trial->grace = 0; }
}

static gboolean
recognition_grace (gpointer data)
{
  Recognition *trial = data;
  trial->grace = 0; trial->failed = TRUE; trial->abandoned = TRUE;
  dprintf (trial->report_fd, "FAIL CANCEL_GRACE\n");
  g_main_loop_quit (trial->loop);
  return G_SOURCE_REMOVE;
}

static void
recognition_cancel (Recognition *trial)
{
  trial->failed = TRUE;
  g_cancellable_cancel (trial->cancel);
  if (!trial->grace) trial->grace = g_timeout_add_seconds (3, recognition_grace, trial);
}

static gboolean
recognition_signal (gpointer data)
{
  Recognition *trial = data;
  trial->interrupted = TRUE;
  recognition_cancel (trial);
  return G_SOURCE_CONTINUE;
}

static gboolean
recognition_deadline (gpointer data)
{
  Recognition *trial = data;
  trial->timer = 0; trial->timed_out = TRUE;
  dprintf (trial->report_fd, "FAIL TIMEOUT\n");
  recognition_cancel (trial);
  return G_SOURCE_REMOVE;
}

static gboolean
recognition_overall (gpointer data)
{
  Recognition *trial = data;
  trial->overall = 0; trial->timed_out = TRUE;
  dprintf (trial->report_fd, "FAIL TIMEOUT\n");
  recognition_cancel (trial);
  return G_SOURCE_REMOVE;
}

static void
recognition_stage (Recognition *trial, const char *stage, guint seconds)
{
  recognition_stop_timer (trial);
  g_clear_object (&trial->cancel); trial->cancel = g_cancellable_new ();
  trial->stage = stage;
  trial->timer = g_timeout_add_seconds (seconds, recognition_deadline, trial);
  dprintf (trial->report_fd, "STAGE %s\n", stage);
}

static void
recognition_closed (GObject *object, GAsyncResult *result, gpointer data)
{
  Recognition *trial = data;
  g_autoptr(GError) error = NULL;
  recognition_stop_timer (trial);
  if (!fp_device_close_finish (FP_DEVICE (object), result, &error)) {
    trial->failed = TRUE; dprintf (trial->report_fd, "FAIL CLOSE\n");
  } else {
    dprintf (trial->report_fd, "CLOSED\n");
    if (!trial->failed) {
      if (trial->enroll) {
        if (trial->progress != 16 || !save_template (trial)) {
          trial->failed = TRUE; dprintf (trial->report_fd, "FAIL OUTPUT\n");
        } else dprintf (trial->report_fd, "RESULT ENROLLED\n");
      } else if (trial->verified && trial->decision && trial->decisions == 1 && !trial->retry)
        dprintf (trial->report_fd, "RESULT %s\n", trial->decision_match ? "MATCH" : "NO_MATCH");
      else { trial->failed = TRUE; dprintf (trial->report_fd, "FAIL DECISION\n"); }
    }
  }
  g_main_loop_quit (trial->loop);
}

static void
recognition_close (Recognition *trial)
{
  trial->closing = TRUE;
  /* The total acquisition limit does not consume the independent close budget. */
  if (trial->overall) { g_source_remove (trial->overall); trial->overall = 0; }
  recognition_stage (trial, "CLOSE", 10);
  fp_device_close (trial->device, trial->cancel, recognition_closed, trial);
}

static void
recognition_error (Recognition *trial, const GError *error, const char *operation)
{
  trial->failed = TRUE;
  if (error && error->domain == FP_DEVICE_RETRY) {
    trial->retry = TRUE; dprintf (trial->report_fd, "FAIL RETRY\n");
  } else if (trial->timed_out) { /* Deadline already reported. */ }
  else if (trial->interrupted || (error && g_error_matches (error, G_IO_ERROR, G_IO_ERROR_CANCELLED)))
    dprintf (trial->report_fd, "FAIL CANCELLED\n");
  else dprintf (trial->report_fd, "FAIL %s\n", operation);
}

static void
recognition_enrolled (GObject *object, GAsyncResult *result, gpointer data)
{
  Recognition *trial = data;
  g_autoptr(GError) error = NULL;
  recognition_stop_timer (trial);
  trial->enrolled = fp_device_enroll_finish (FP_DEVICE (object), result, &error);
  if (!trial->enrolled || trial->failed) recognition_error (trial, error, "ENROLL");
  recognition_close (trial);
}

static void
recognition_verified (GObject *object, GAsyncResult *result, gpointer data)
{
  Recognition *trial = data;
  g_autoptr(GError) error = NULL;
  gboolean match = FALSE;
  recognition_stop_timer (trial);
  gboolean ok = fp_device_verify_finish (FP_DEVICE (object), result, &match, NULL, &error);
  if (!ok || trial->failed) recognition_error (trial, error, "VERIFY");
  else if (trial->retry || !trial->decision || trial->decisions != 1 || match != trial->decision_match) {
    trial->failed = TRUE; dprintf (trial->report_fd, "FAIL DECISION\n");
  } else trial->verified = TRUE;
  recognition_close (trial);
}

static void
recognition_match (FpDevice *device, FpPrint *match, FpPrint *print, gpointer data, GError *error)
{
  Recognition *trial = data;
  (void) device; (void) print;
  trial->decisions++;
  if (error) { trial->retry = TRUE; }
  else {
    trial->decision = TRUE; trial->decision_match = match != NULL;
    if (match && match != trial->template) trial->failed = TRUE;
  }
  /* Deliberately withhold MATCH until completion and successful close. */
  dprintf (trial->report_fd, "PROMPT LIFT\n");
}

static void
recognition_progress (FpDevice *device, gint completed, FpPrint *print, gpointer data, GError *error)
{
  Recognition *trial = data;
  (void) device; (void) print;
  if (trial->failed) return;
  if (error) {
    trial->retries++;
    dprintf (trial->report_fd, "RETRY SCAN\n");
    if (trial->retries > 32) { dprintf (trial->report_fd, "FAIL RETRY_LIMIT\n"); recognition_cancel (trial); }
  } else if (completed < 1 || completed > 16 || (guint) completed != trial->progress + 1) {
    dprintf (trial->report_fd, "FAIL PROGRESS\n"); recognition_cancel (trial);
  } else {
    trial->progress = (guint) completed;
    dprintf (trial->report_fd, "PROGRESS %u 16\n", trial->progress);
  }
  if (!trial->failed && !error) {
    if (trial->timer) g_source_remove (trial->timer);
    trial->timer = g_timeout_add_seconds (45, recognition_deadline, trial);
  }
  dprintf (trial->report_fd, "PROMPT LIFT\n");
}

static void
recognition_prompt (Recognition *trial, FpFingerStatusFlags status)
{
  if (!trial->stage || (strcmp (trial->stage, "ENROLL") && strcmp (trial->stage, "VERIFY"))) return;
  if (status & FP_FINGER_STATUS_PRESENT) { trial->seen_present = TRUE; trial->touch_prompted = FALSE; }
  else trial->lift_prompted = FALSE;
  if (trial->enroll && trial->seen_present && !(status & FP_FINGER_STATUS_PRESENT) &&
      (status & FP_FINGER_STATUS_NEEDED) && !trial->touch_prompted) {
    trial->touch_prompted = TRUE; dprintf (trial->report_fd, "PROMPT TOUCH\n");
  }
  if ((status & FP_FINGER_STATUS_PRESENT) && !(status & FP_FINGER_STATUS_NEEDED) && !trial->lift_prompted) {
    trial->lift_prompted = TRUE; dprintf (trial->report_fd, "PROMPT LIFT\n");
  }
}

static void
recognition_finger (GObject *object, GParamSpec *spec, gpointer data)
{
  (void) spec;
  recognition_prompt (data, fp_device_get_finger_status (FP_DEVICE (object)));
}

static void
recognition_opened (GObject *object, GAsyncResult *result, gpointer data)
{
  Recognition *trial = data;
  g_autoptr(GError) error = NULL;
  recognition_stop_timer (trial);
  if (!fp_device_open_finish (FP_DEVICE (object), result, &error)) {
    recognition_error (trial, error, "OPEN"); g_main_loop_quit (trial->loop); return;
  }
  if (trial->failed) { recognition_close (trial); return; }
  trial->overall = g_timeout_add_seconds (trial->enroll ? 600 : 45, recognition_overall, trial);
  recognition_stage (trial, trial->enroll ? "ENROLL" : "VERIFY", 45);
  if (trial->enroll) {
    trial->template = g_object_ref_sink (fp_print_new (trial->device));
    fp_print_set_finger (trial->template, FP_FINGER_RIGHT_INDEX);
    fp_device_enroll (trial->device, trial->template, trial->cancel,
                      recognition_progress, trial, NULL, recognition_enrolled, trial);
  } else fp_device_verify (trial->device, trial->template, trial->cancel,
                           recognition_match, trial, NULL, recognition_verified, trial);
}

static void
recognition_initialized (GObject *object, GAsyncResult *result, gpointer data)
{
  Recognition *trial = data;
  g_autoptr(GError) error = NULL;
  recognition_stop_timer (trial);
  trial->device = FP_DEVICE (g_async_initable_new_finish (G_ASYNC_INITABLE (object), result, &error));
  if (!trial->device || trial->failed) {
    recognition_error (trial, error, "INIT"); g_main_loop_quit (trial->loop); return;
  }
  if (strcmp (fp_device_get_driver (trial->device), "goodixtls55x4") != 0 ||
      !(fp_device_get_features (trial->device) & FP_DEVICE_FEATURE_VERIFY) ||
      (fp_device_get_features (trial->device) & FP_DEVICE_FEATURE_STORAGE) ||
      fp_device_get_nr_enroll_stages (trial->device) != 16 ||
      (!trial->enroll && !fp_print_compatible (trial->template, trial->device))) {
    trial->failed = TRUE; dprintf (trial->report_fd, "FAIL DRIVER\n");
    g_main_loop_quit (trial->loop); return;
  }
  g_signal_connect (trial->device, "notify::finger-status", G_CALLBACK (recognition_finger), trial);
  recognition_stage (trial, "OPEN", 15);
  fp_device_open (trial->device, trial->cancel, recognition_opened, trial);
}

static gboolean
recognition_selftest (int report_fd)
{
  /* This fixture is artificial keypoints/descriptors, never a sensor image.
   * The reviewed SIGFM binary format is host-native, used only on x86_64. */
  g_autoptr(GByteArray) binary = g_byte_array_new ();
  size_t count = 6;
  g_byte_array_append (binary, (guint8 *) &count, sizeof count);
  for (guint i = 0; i < count; i++) {
    gint class_id = -1, octave = 0;
    float angle = -1, response = 1, size = 8, x = (float) (i % 3) * 10, y = (float) (i / 3) * 10;
    g_byte_array_append (binary, (guint8 *) &class_id, 4);
    g_byte_array_append (binary, (guint8 *) &angle, 4);
    g_byte_array_append (binary, (guint8 *) &octave, 4);
    g_byte_array_append (binary, (guint8 *) &response, 4);
    g_byte_array_append (binary, (guint8 *) &size, 4);
    g_byte_array_append (binary, (guint8 *) &x, 4);
    g_byte_array_append (binary, (guint8 *) &y, 4);
  }
  gint type = 5, rows = (gint) count, columns = 128;
  g_byte_array_append (binary, (guint8 *) &type, 4);
  g_byte_array_append (binary, (guint8 *) &rows, 4);
  g_byte_array_append (binary, (guint8 *) &columns, 4);
  for (guint i = 0; i < count; i++) for (guint j = 0; j < 128; j++) {
    float value = i == j ? 1 : 0;
    g_byte_array_append (binary, (guint8 *) &value, 4);
  }
  GVariantBuilder prints;
  g_variant_builder_init (&prints, G_VARIANT_TYPE ("a(ay)"));
  g_variant_builder_add (&prints, "(@ay)",
    g_variant_new_fixed_array (G_VARIANT_TYPE_BYTE, binary->data, binary->len, 1));
  GVariantBuilder empty;
  g_variant_builder_init (&empty, G_VARIANT_TYPE_VARDICT);
  g_autoptr(GVariant) value = g_variant_ref_sink (g_variant_new (
    "(issbymsmsi@a{sv}v)", REVIEWED_SIGFM_TYPE, "goodixtls55x4", "synthetic",
    FALSE, (guchar) FP_FINGER_RIGHT_INDEX, NULL, NULL, G_MININT32,
    g_variant_builder_end (&empty), g_variant_new ("(@a(ay))", g_variant_builder_end (&prints))));
  gsize length = g_variant_get_size (value);
  g_autofree guchar *bytes = g_malloc (length + 3);
  memcpy (bytes, "FP3", 3);
  /* FP3 puts the variant at an unaligned offset: copy its serialized bytes. */
  memcpy (bytes + 3, g_variant_get_data (value), length);
  g_autoptr(GError) error = NULL;
  g_autoptr(FpPrint) first = fp_print_deserialize (bytes, length + 3, &error);
  if (!valid_template (first)) return FALSE;
  g_autofree guchar *serialized = NULL;
  gsize serialized_length = 0;
  if (!fp_print_serialize (first, &serialized, &serialized_length, &error)) return FALSE;
  g_autoptr(FpPrint) second = fp_print_deserialize (serialized, serialized_length, &error);
  if (!valid_template (second)) return FALSE;
  g_autofree guchar *again = NULL;
  gsize again_length = 0;
  if (!fp_print_serialize (second, &again, &again_length, &error) || again_length != serialized_length ||
      memcmp (again, serialized, again_length)) return FALSE;
  fp_print_set_finger (second, FP_FINGER_LEFT_INDEX);
  if (valid_template (second) || valid_template (NULL)) return FALSE;
  if (!test_bulk_interface ()) return FALSE;
  Recognition prompt = {.enroll = TRUE, .report_fd = report_fd, .stage = "ENROLL"};
  recognition_prompt (&prompt, FP_FINGER_STATUS_NEEDED);
  if (prompt.seen_present || prompt.touch_prompted || prompt.lift_prompted) return FALSE;
  recognition_prompt (&prompt, FP_FINGER_STATUS_NEEDED | FP_FINGER_STATUS_PRESENT);
  if (!prompt.seen_present || prompt.touch_prompted || prompt.lift_prompted) return FALSE;
  recognition_prompt (&prompt, FP_FINGER_STATUS_PRESENT);
  if (!prompt.lift_prompted || prompt.touch_prompted) return FALSE;
  recognition_prompt (&prompt, FP_FINGER_STATUS_NONE);
  if (prompt.lift_prompted || prompt.touch_prompted) return FALSE;
  recognition_prompt (&prompt, FP_FINGER_STATUS_NEEDED);
  if (!prompt.touch_prompted || prompt.lift_prompted) return FALSE;
  recognition_prompt (&prompt, FP_FINGER_STATUS_NEEDED);
  Recognition timeout = {.loop = g_main_loop_new (NULL, FALSE), .cancel = g_cancellable_new (), .report_fd = report_fd};
  recognition_deadline (&timeout);
  if (!timeout.failed || !timeout.timed_out || !g_cancellable_is_cancelled (timeout.cancel) || !timeout.grace) return FALSE;
  recognition_stop_timer (&timeout); g_object_unref (timeout.cancel); g_main_loop_unref (timeout.loop);
  dprintf (report_fd, "SELFTEST TEMPLATE_ROUNDTRIP_PASS\n");
  return TRUE;
}

int
main (int argc, char **argv)
{
  if (argc == 3 && !strcmp (argv[1], "--self-test")) {
    unsigned long report;
    if (!number (argv[2], &report)) return 2;
    return recognition_selftest ((int) report) ? 0 : 1;
  }
  unsigned long report, directory, template_fd, uid, gid;
  if (argc != 7 || (strcmp (argv[1], "enroll") && strcmp (argv[1], "verify")) ||
      !number (argv[2], &report) || !number (argv[3], &directory) ||
      !number (argv[4], &template_fd) || !number (argv[5], &uid) || !number (argv[6], &gid)) return 2;
  struct stat output;
  struct rlimit core = {0, 0};
  if (setrlimit (RLIMIT_CORE, &core) != 0 || fstat ((int) directory, &output) ||
      !S_ISDIR (output.st_mode) || (output.st_mode & 0777) != 0700 || output.st_uid != (uid_t) uid) return 2;
  umask (077);
  g_set_print_handler (quiet_print); g_set_printerr_handler (quiet_print);
  g_log_set_default_handler (quiet_log, NULL); g_log_set_writer_func (quiet_writer, NULL, NULL);
  Recognition trial = {.enroll = !strcmp (argv[1], "enroll"), .report_fd = (int) report,
                       .directory_fd = (int) directory, .owner = (uid_t) uid, .group = (gid_t) gid};
  if (!trial.enroll) {
    trial.template = read_template ((int) template_fd);
    if (!trial.template) { dprintf (trial.report_fd, "FAIL TEMPLATE\n"); return 1; }
  }
  g_autoptr(GError) error = NULL;
  g_autoptr(GUsbContext) context = g_usb_context_new (&error);
  if (!context) { dprintf (trial.report_fd, "FAIL DISCOVERY\n"); return 1; }
  g_usb_context_set_flags (context, G_USB_CONTEXT_FLAGS_NONE);
  g_usb_context_enumerate (context);
  GPtrArray *devices = g_usb_context_get_devices (context);
  GUsbDevice *usb = NULL; guint matches = 0;
  for (guint i = 0; i < devices->len; i++) {
    GUsbDevice *candidate = g_ptr_array_index (devices, i);
    if (g_usb_device_get_vid (candidate) == 0x27c6 && g_usb_device_get_pid (candidate) == 0x55a4) { usb = candidate; matches++; }
  }
  if (matches != 1) { dprintf (trial.report_fd, "FAIL %s\n", matches ? "USB_MULTIPLE" : "USB_MISSING"); return 1; }
  if (!validate_interface (usb, trial.report_fd)) return 1;
  trial.loop = g_main_loop_new (NULL, FALSE);
  trial.signal_int = g_unix_signal_add (SIGINT, recognition_signal, &trial);
  trial.signal_term = g_unix_signal_add (SIGTERM, recognition_signal, &trial);
  recognition_stage (&trial, "INIT", 10);
  g_async_initable_new_async (fpi_device_goodixtls55x4_get_type (), G_PRIORITY_DEFAULT,
                              trial.cancel, recognition_initialized, &trial,
                              "fpi-usb-device", usb, "fpi-driver-data", (guint64) 1, NULL);
  g_main_loop_run (trial.loop);
  recognition_stop_timer (&trial);
  if (trial.overall) g_source_remove (trial.overall);
  g_source_remove (trial.signal_int); g_source_remove (trial.signal_term);
  /* Outstanding callbacks must never observe freed state after cancellation. */
  if (trial.abandoned || (trial.device && fp_device_is_open (trial.device))) _exit (1);
  g_clear_object (&trial.enrolled); g_clear_object (&trial.template);
  g_clear_object (&trial.device); g_clear_object (&trial.cancel); g_main_loop_unref (trial.loop);
  return trial.failed ? 1 : 0;
}
