/* The production matcher body is inserted by the offline runner. Real GLib
 * arrays/errors; minimal print and error-domain stand-ins, no GObject device. */
#include <gio/gio.h>
#include <stdarg.h>
#include "sigfm.hpp"
typedef enum { FPI_PRINT_UNDEFINED, FPI_PRINT_RAW, FPI_PRINT_NBIS, FPI_PRINT_SIGFM } FpiPrintType;
typedef enum { FPI_MATCH_ERROR=-1, FPI_MATCH_FAIL, FPI_MATCH_SUCCESS } FpiMatchResult;
typedef struct { FpiPrintType type; GPtrArray *prints; } FpPrint;
#define FP_DEVICE_ERROR g_quark_from_static_string("offline-device-error")
#define FP_DEVICE_ERROR_NOT_SUPPORTED 1
#define FP_DEVICE_ERROR_DATA_INVALID 2
#define fp_dbg(...) ((void)0)
static GError *fpi_device_error_new_msg(int code, const char *format, ...)
{
  va_list args; va_start(args,format);
  GError *error=g_error_new_valist(FP_DEVICE_ERROR,code,format,args);
  va_end(args); return error;
}
/* INSERT MATCH IMPLEMENTATION */
int test_print_match(SigfmImgInfo *a, SigfmImgInfo *b, int na, int nb, int threshold)
{
  GError *error=NULL;
  FpPrint tmpl={FPI_PRINT_SIGFM,g_ptr_array_new()}, probe={FPI_PRINT_SIGFM,g_ptr_array_new()};
  for(int i=0;i<na;i++) g_ptr_array_add(tmpl.prints,a);
  for(int i=0;i<nb;i++) g_ptr_array_add(probe.prints,b);
  int result=fpi_print_sigfm_match(&tmpl,&probe,threshold,&error);
  g_assert_cmpint(error!=NULL,==,result==FPI_MATCH_ERROR);
  g_clear_error(&error); g_ptr_array_unref(tmpl.prints);g_ptr_array_unref(probe.prints);
  return result;
}
