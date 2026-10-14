/* SPDX-License-Identifier: MIT
 * Synthetic public-API stub: no device, image, template, USB or daemon. */
#include <fprint.h>
#include <stdlib.h>

gboolean
fp_device_verify_finish (FpDevice *device, GAsyncResult *result, gboolean *match,
                         FpPrint **print, GError **error)
{
  (void) device; (void) result; (void) print;
  int mode = atoi (getenv ("SYNTHETIC_VERIFY"));
  if (mode == 2) {
    g_set_error_literal (error, G_IO_ERROR, G_IO_ERROR_CANCELLED, "synthetic cancellation");
    return FALSE;
  }
  if (match) *match = mode == 0;
  return TRUE;
}

gboolean
fp_device_close_finish (FpDevice *device, GAsyncResult *result, GError **error)
{
  (void) device; (void) result;
  if (atoi (getenv ("SYNTHETIC_CLOSE"))) {
    g_set_error_literal (error, G_IO_ERROR, G_IO_ERROR_FAILED, "synthetic close failure");
    return FALSE;
  }
  return TRUE;
}
