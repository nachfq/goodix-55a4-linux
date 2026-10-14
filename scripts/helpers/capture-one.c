/* SPDX-License-Identifier: MIT
 * Standalone experiment using the public libfprint asynchronous API.
 * This file is original project code; the separately linked driver is LGPL-2.1+.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <gio/gio.h>
#include <glib-unix.h>
#include <gusb.h>
#include <libusb.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <unistd.h>
#include "fp-device.h"

/* Explicitly exported only by our reviewed experimental library variant. */
extern GType fpi_device_goodixtls55x4_get_type (void);

typedef struct {
  GMainLoop *loop;
  GCancellable *cancel;
  FpDevice *device;
  FpImage *image;
  guint timer, grace;
  int report_fd, directory_fd;
  uid_t owner;
  gid_t group;
  const char *stage;
  gboolean failed, closing, abandoned, self_test, lift_prompted;
} Trial;

static void
quiet_print (const gchar *message) { (void) message; }
static void
quiet_log (const gchar *domain, GLogLevelFlags level, const gchar *message,
           gpointer data) { (void) domain; (void) level; (void) message; (void) data; }
static GLogWriterOutput
quiet_writer (GLogLevelFlags level, const GLogField *fields, gsize count,
              gpointer data) { (void) level; (void) fields; (void) count; (void) data; return G_LOG_WRITER_HANDLED; }

static gboolean
write_all (int fd, const void *data, size_t size)
{
  const unsigned char *bytes = data;
  while (size) {
    ssize_t n = write (fd, bytes, size);
    if (n < 0 && errno == EINTR) continue;
    if (n <= 0) return FALSE;
    bytes += n; size -= (size_t) n;
  }
  return TRUE;
}

static gboolean
save_image (Trial *trial)
{
  guint w = fp_image_get_width (trial->image), h = fp_image_get_height (trial->image);
  gsize count = 0;
  const guchar *pixels = fp_image_get_data (trial->image, &count);
  char header[64];
  if (!w || !h || w > 4096 || h > 4096 || count != (gsize) w * h || !pixels)
    return FALSE;
  int fd = openat (trial->directory_fd, "image.pgm", O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
  if (fd < 0) return FALSE;
  int length = snprintf (header, sizeof header, "P5\n%u %u\n255\n", w, h);
  gboolean ok = fchmod (fd, 0600) == 0 && fchown (fd, trial->owner, trial->group) == 0 &&
                write_all (fd, header, (size_t) length) && write_all (fd, pixels, count) && fsync (fd) == 0;
  if (close (fd) != 0) ok = FALSE;
  if (!ok) unlinkat (trial->directory_fd, "image.pgm", 0);
  else dprintf (trial->report_fd, "%s IMAGE %u %u\n",
                trial->self_test ? "SELFTEST" : "RESULT", w, h);
  return ok;
}

static void
stop_timer (Trial *trial)
{
  if (trial->timer) { g_source_remove (trial->timer); trial->timer = 0; }
  if (trial->grace) { g_source_remove (trial->grace); trial->grace = 0; }
}

static gboolean
cancel_grace (gpointer data)
{
  Trial *trial = data;
  trial->grace = 0;
  trial->failed = TRUE;
  trial->abandoned = TRUE;
  dprintf (trial->report_fd, "FAIL CANCEL_GRACE\n");
  g_main_loop_quit (trial->loop);
  return G_SOURCE_REMOVE;
}

static gboolean
cancel_trial (gpointer data)
{
  Trial *trial = data;
  trial->failed = TRUE;
  g_cancellable_cancel (trial->cancel);
  if (!trial->grace) trial->grace = g_timeout_add_seconds (3, cancel_grace, trial);
  return G_SOURCE_CONTINUE;
}

static gboolean
deadline (gpointer data)
{
  Trial *trial = data;
  trial->timer = 0;
  cancel_trial (trial);
  return G_SOURCE_REMOVE;
}

static void
begin_stage (Trial *trial, const char *stage, guint seconds)
{
  stop_timer (trial);
  g_clear_object (&trial->cancel);
  trial->cancel = g_cancellable_new ();
  trial->stage = stage;
  trial->timer = g_timeout_add_seconds (seconds, deadline, trial);
  dprintf (trial->report_fd, "STAGE %s\n", stage);
}

static void
closed (GObject *object, GAsyncResult *result, gpointer data)
{
  Trial *trial = data;
  g_autoptr(GError) error = NULL;
  stop_timer (trial);
  if (!fp_device_close_finish (FP_DEVICE (object), result, &error)) {
    trial->failed = TRUE;
    dprintf (trial->report_fd, "FAIL CLOSE\n");
  } else {
    dprintf (trial->report_fd, "CLOSED\n");
    if (!trial->failed && trial->image && !save_image (trial)) {
      trial->failed = TRUE;
      dprintf (trial->report_fd, "FAIL OUTPUT\n");
    }
  }
  g_main_loop_quit (trial->loop);
}

static void
close_device (Trial *trial)
{
  trial->closing = TRUE;
  begin_stage (trial, "CLOSE", 10);
  fp_device_close (trial->device, trial->cancel, closed, trial);
}

static void
captured (GObject *object, GAsyncResult *result, gpointer data)
{
  Trial *trial = data;
  g_autoptr(GError) error = NULL;
  stop_timer (trial);
  trial->image = fp_device_capture_finish (FP_DEVICE (object), result, &error);
  if (!trial->image) { trial->failed = TRUE; dprintf (trial->report_fd, "FAIL CAPTURE\n"); }
  close_device (trial);
}

static void
prompt_finger_status (Trial *trial, FpFingerStatusFlags status)
{
  /* NEEDED is also emitted before calibration; it is not a touch-ready signal.
   * Removing NEEDED while PRESENT asks for lift before capture_finish can run. */
  if (trial->stage && strcmp (trial->stage, "CAPTURE") == 0 &&
      (status & FP_FINGER_STATUS_PRESENT) && !(status & FP_FINGER_STATUS_NEEDED) &&
      !trial->lift_prompted) {
    trial->lift_prompted = TRUE;
    dprintf (trial->report_fd, "%s LIFT\n", trial->self_test ? "SELFTEST PROMPT" : "PROMPT");
  }
}

static void
finger_status_changed (GObject *object, GParamSpec *spec, gpointer data)
{
  (void) spec;
  prompt_finger_status (data, fp_device_get_finger_status (FP_DEVICE (object)));
}

static void
opened (GObject *object, GAsyncResult *result, gpointer data)
{
  Trial *trial = data;
  g_autoptr(GError) error = NULL;
  stop_timer (trial);
  if (!fp_device_open_finish (FP_DEVICE (object), result, &error)) {
    trial->failed = TRUE; dprintf (trial->report_fd, "FAIL OPEN\n");
    g_main_loop_quit (trial->loop); return;
  }
  if (trial->failed) { close_device (trial); return; }
  trial->lift_prompted = FALSE;
  begin_stage (trial, "CAPTURE", 45);
  fp_device_capture (trial->device, TRUE, trial->cancel, captured, trial);
}

static void
initialized (GObject *object, GAsyncResult *result, gpointer data)
{
  Trial *trial = data;
  g_autoptr(GError) error = NULL;
  stop_timer (trial);
  trial->device = FP_DEVICE (g_async_initable_new_finish (G_ASYNC_INITABLE (object), result, &error));
  if (!trial->device || trial->failed) {
    trial->failed = TRUE; dprintf (trial->report_fd, "FAIL INIT\n");
    g_main_loop_quit (trial->loop); return;
  }
  if (strcmp (fp_device_get_driver (trial->device), "goodixtls55x4") != 0 ||
      !(fp_device_get_features (trial->device) & FP_DEVICE_FEATURE_CAPTURE)) {
    trial->failed = TRUE; dprintf (trial->report_fd, "FAIL DRIVER\n");
    g_main_loop_quit (trial->loop); return;
  }
  g_signal_connect (trial->device, "notify::finger-status", G_CALLBACK (finger_status_changed), trial);
  begin_stage (trial, "OPEN", 15);
  fp_device_open (trial->device, trial->cancel, opened, trial);
}

static gboolean
valid_bulk_interface (const struct libusb_config_descriptor *configuration)
{
  guint matches = 0;
  if (!configuration || !configuration->bConfigurationValue) return FALSE;
  for (guint i = 0; i < configuration->bNumInterfaces; i++) {
    const struct libusb_interface *group = &configuration->interface[i];
    for (int j = 0; j < group->num_altsetting; j++) {
      const struct libusb_interface_descriptor *interface = &group->altsetting[j];
      if (interface->bInterfaceNumber != 0 || interface->bAlternateSetting != 0)
        continue;
      if ((interface->bInterfaceClass != 0xff && interface->bInterfaceClass != 0x0a) ||
          interface->bNumEndpoints != 2 || !interface->endpoint) return FALSE;
      gboolean in = FALSE, out = FALSE;
      for (guint k = 0; k < interface->bNumEndpoints; k++) {
        const struct libusb_endpoint_descriptor *endpoint = &interface->endpoint[k];
        /* GUsb get_kind() returns bDescriptorType, not bmAttributes. */
        if (endpoint->bDescriptorType != LIBUSB_DT_ENDPOINT ||
            (endpoint->bmAttributes & LIBUSB_TRANSFER_TYPE_MASK) != LIBUSB_TRANSFER_TYPE_BULK)
          return FALSE;
        in |= endpoint->bEndpointAddress == 0x82;
        out |= endpoint->bEndpointAddress == 0x01;
      }
      if (!in || !out) return FALSE;
      matches++;
    }
  }
  return matches == 1;
}

static gboolean
validate_interface (GUsbDevice *usb, int report_fd)
{
  g_autoptr(GError) error = NULL;
  gboolean ok = FALSE;
  libusb_context *context = NULL;
  libusb_device **devices = NULL;
  struct libusb_config_descriptor *descriptor = NULL;
  const char *failure = "USB_CONFIGURATION";
  if (!g_usb_device_open (usb, &error)) {
    dprintf (report_fd, "FAIL USB_OPEN\n");
    return FALSE;
  }
  int configuration = g_usb_device_get_configuration (usb, &error);
  if (configuration > 0 && !error) {
    failure = "USB_DESCRIPTORS";
    if (libusb_init (&context) == 0) {
      ssize_t count = libusb_get_device_list (context, &devices);
      guint matches = 0;
      for (ssize_t i = 0; i < count; i++) {
        if (libusb_get_bus_number (devices[i]) != g_usb_device_get_bus (usb) ||
            libusb_get_device_address (devices[i]) != g_usb_device_get_address (usb)) continue;
        struct libusb_device_descriptor identity;
        if (libusb_get_device_descriptor (devices[i], &identity) != 0 ||
            identity.idVendor != 0x27c6 || identity.idProduct != 0x55a4) continue;
        matches++;
        if (libusb_get_active_config_descriptor (devices[i], &descriptor) == 0 &&
            descriptor->bConfigurationValue == configuration) {
          failure = "USB_LAYOUT";
          ok = valid_bulk_interface (descriptor);
        }
      }
      ok = ok && matches == 1;
    }
  }
  if (descriptor) libusb_free_config_descriptor (descriptor);
  if (devices) libusb_free_device_list (devices, 1);
  if (context) libusb_exit (context);
  g_clear_error (&error);
  if (!g_usb_device_close (usb, &error)) { ok = FALSE; failure = "USB_PRECHECK_CLOSE"; }
  if (!ok) dprintf (report_fd, "FAIL %s\n", failure);
  return ok;
}

static gboolean
test_bulk_interface (void)
{
  struct libusb_endpoint_descriptor endpoints[2] = {
    {.bDescriptorType = LIBUSB_DT_ENDPOINT, .bEndpointAddress = 0x82, .bmAttributes = LIBUSB_TRANSFER_TYPE_BULK},
    {.bDescriptorType = LIBUSB_DT_ENDPOINT, .bEndpointAddress = 0x01, .bmAttributes = LIBUSB_TRANSFER_TYPE_BULK}
  };
  struct libusb_interface_descriptor alternate = {
    .bInterfaceNumber = 0, .bAlternateSetting = 0, .bInterfaceClass = 0xff,
    .bNumEndpoints = 2, .endpoint = endpoints
  };
  struct libusb_interface group = {.num_altsetting = 1, .altsetting = &alternate};
  struct libusb_config_descriptor configuration = {
    .bConfigurationValue = 1, .bNumInterfaces = 1, .interface = &group
  };
  /* A valid endpoint's descriptor type is 5, while its transfer type is 2.
   * The former check (5 & 3) == 2 rejects this valid layout. */
  if (!valid_bulk_interface (&configuration)) return FALSE;
  endpoints[0].bmAttributes = LIBUSB_TRANSFER_TYPE_INTERRUPT;
  if (valid_bulk_interface (&configuration)) return FALSE;
  endpoints[0].bmAttributes = LIBUSB_TRANSFER_TYPE_BULK;
  endpoints[0].bEndpointAddress = 0x83;
  if (valid_bulk_interface (&configuration)) return FALSE;
  endpoints[0].bEndpointAddress = 0x82;
  alternate.bNumEndpoints = 1;
  if (valid_bulk_interface (&configuration)) return FALSE;
  alternate.bNumEndpoints = 2;
  alternate.bAlternateSetting = 1;
  if (valid_bulk_interface (&configuration)) return FALSE;
  alternate.bAlternateSetting = 0;
  alternate.bInterfaceClass = 3;
  if (valid_bulk_interface (&configuration)) return FALSE;
  alternate.bInterfaceClass = 0x0a;
  if (!valid_bulk_interface (&configuration)) return FALSE;
  configuration.bConfigurationValue = 0;
  if (valid_bulk_interface (&configuration) || valid_bulk_interface (NULL)) return FALSE;
  return TRUE;
}

static gboolean
number (const char *text, unsigned long *value)
{
  char *end = NULL;
  if (!text || !*text || *text == '-') return FALSE;
  errno = 0; *value = strtoul (text, &end, 10);
  return !errno && end && !*end && *value <= G_MAXINT;
}

int
main (int argc, char **argv)
{
  gboolean self_test = argc == 6 && strcmp (argv[1], "--self-test") == 0;
  if (self_test) { argv++; argc--; }
  unsigned long report, directory, uid, gid;
  struct stat output;
  struct rlimit core = {0, 0};
  if (argc != 5 || !number (argv[1], &report) || !number (argv[2], &directory) ||
      !number (argv[3], &uid) || !number (argv[4], &gid)) return 2;
  if (setrlimit (RLIMIT_CORE, &core) != 0) return 2;
  umask (077);
  if (fstat ((int) directory, &output) != 0 || !S_ISDIR (output.st_mode) ||
      (output.st_mode & 0777) != 0700 || output.st_uid != (uid_t) uid) return 2;
  g_set_print_handler (quiet_print); g_set_printerr_handler (quiet_print);
  g_log_set_default_handler (quiet_log, NULL); g_log_set_writer_func (quiet_writer, NULL, NULL);
  if (self_test) {
    if (!test_bulk_interface ()) return 1;
    /* No USB context/device is constructed. Distinct reports cannot be mistaken
     * for a successful physical capture by the parent launcher's parser. */
    Trial synthetic = {.report_fd = (int) report, .directory_fd = (int) directory,
                       .owner = (uid_t) uid, .group = (gid_t) gid, .self_test = TRUE};
    /* Exercise the actual prompt gate with synthetic flags, not a USB device. */
    synthetic.stage = "OPEN";
    prompt_finger_status (&synthetic, FP_FINGER_STATUS_PRESENT);
    if (synthetic.lift_prompted) return 1;
    synthetic.stage = "CAPTURE";
    prompt_finger_status (&synthetic, FP_FINGER_STATUS_NEEDED);
    prompt_finger_status (&synthetic, FP_FINGER_STATUS_PRESENT | FP_FINGER_STATUS_NEEDED);
    if (synthetic.lift_prompted) return 1;
    prompt_finger_status (&synthetic, FP_FINGER_STATUS_PRESENT);
    if (!synthetic.lift_prompted) return 1;
    prompt_finger_status (&synthetic, FP_FINGER_STATUS_PRESENT); /* No second prompt. */
    synthetic.image = fp_image_new (2, 2);
    if (!synthetic.image) return 1;
    gsize count = 0;
    const guint8 pattern[] = {0, 64, 128, 255};
    const guchar *pixels = fp_image_get_data (synthetic.image, &count);
    if (!pixels || count != sizeof pattern) { g_object_unref (synthetic.image); return 1; }
    memcpy ((gpointer) pixels, pattern, sizeof pattern);
    gboolean first = save_image (&synthetic);
    gboolean overwrite_refused = !save_image (&synthetic);
    g_object_unref (synthetic.image);
    if (first && overwrite_refused) {
      dprintf ((int) report, "SELFTEST EXCLUSIVE_OUTPUT_PASS\n");
      return 0;
    }
    dprintf ((int) report, "SELFTEST OUTPUT_REFUSED\n");
    return 1;
  }
  g_autoptr(GError) error = NULL;
  g_autoptr(GUsbContext) context = g_usb_context_new (&error);
  if (!context) { dprintf ((int) report, "FAIL DISCOVERY\n"); return 1; }
  g_usb_context_set_flags (context, G_USB_CONTEXT_FLAGS_NONE);
  /* USB descriptors are inventoried, but only this exact device is opened. */
  g_usb_context_enumerate (context);
  GPtrArray *devices = g_usb_context_get_devices (context);
  GUsbDevice *usb = NULL;
  guint count = 0;
  for (guint i = 0; i < devices->len; i++) {
    GUsbDevice *candidate = g_ptr_array_index (devices, i);
    if (g_usb_device_get_vid (candidate) == 0x27c6 && g_usb_device_get_pid (candidate) == 0x55a4) {
      usb = candidate; count++;
    }
  }
  if (count != 1) {
    dprintf ((int) report, "FAIL %s\n", count ? "USB_MULTIPLE" : "USB_MISSING");
    return 1;
  }
  if (!validate_interface (usb, (int) report)) return 1;
  Trial trial = {.report_fd = (int) report, .directory_fd = (int) directory,
                 .owner = (uid_t) uid, .group = (gid_t) gid};
  trial.loop = g_main_loop_new (NULL, FALSE);
  begin_stage (&trial, "INIT", 10);
  guint sigint = g_unix_signal_add (SIGINT, cancel_trial, &trial);
  guint sigterm = g_unix_signal_add (SIGTERM, cancel_trial, &trial);
  g_async_initable_new_async (fpi_device_goodixtls55x4_get_type (), G_PRIORITY_DEFAULT,
                              trial.cancel, initialized, &trial,
                              "fpi-usb-device", usb, "fpi-driver-data", (guint64) 1, NULL);
  g_main_loop_run (trial.loop);
  stop_timer (&trial);
  g_source_remove (sigint); g_source_remove (sigterm);
  if (trial.abandoned) _exit (1);
  /* If cancellation grace expired, do not free objects with outstanding callbacks.
   * Process exit releases handles; the parent still has a hard wall-clock deadline. */
  if (!trial.failed || trial.closing) {
    /* Avoid object teardown after an incomplete close; process exit is bounded. */
    if (!fp_device_is_open (trial.device)) {
      g_clear_object (&trial.image); g_clear_object (&trial.device);
      g_clear_object (&trial.cancel); g_main_loop_unref (trial.loop);
    }
  }
  return trial.failed ? 1 : 0;
}
