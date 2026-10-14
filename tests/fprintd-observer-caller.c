/* SPDX-License-Identifier: MIT -- call synthetic versioned public symbols. */
#include <fprint.h>
#include <stdlib.h>

int main (void)
{
  gboolean match = FALSE;
  GError *error = NULL;
  int verify = atoi (getenv ("SYNTHETIC_VERIFY"));
  gboolean ok = fp_device_verify_finish (NULL, NULL, &match, NULL, &error);
  if (ok != (verify != 2) || (ok && match != (verify == 0)) ||
      (!ok && !g_error_matches (error, G_IO_ERROR, G_IO_ERROR_CANCELLED))) return 1;
  g_clear_error (&error);
  int close = atoi (getenv ("SYNTHETIC_CLOSE"));
  ok = fp_device_close_finish (NULL, NULL, &error);
  if (ok != !close || (!ok && !g_error_matches (error, G_IO_ERROR, G_IO_ERROR_FAILED))) return 1;
  g_clear_error (&error);
  return 0;
}
