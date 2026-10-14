#!/usr/bin/env python3
"""Offline real-TLS lifecycle tests of the capture source variant; no USB."""
import argparse
import importlib.util
import os
from pathlib import Path
import resource
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'work/libfprint-capture-fixed/libfprint/drivers/goodixtls'
CASES = ('partial-init', 'real-tls', 'flight-fragmentation', 'silent-timeout', 'stop-join')


def check_inputs():
    spec = importlib.util.spec_from_file_location('capture_build', ROOT / 'scripts/11-build-capture.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.check_inputs()
    # The extended flow harness deliberately reuses the previous runner/fixture.
    spec = importlib.util.spec_from_file_location('previous_flow', ROOT / 'scripts/07-test-tls-flow.py')
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    previous.check_inputs()


def unit():
    header = (SOURCE / 'goodixtls.h').read_text()
    types = header[header.index('struct _GoodixTlsServer;'):header.index('// This is called only once to init')]
    source = (SOURCE / 'goodixtls.c').read_text()
    # Real implementation bodies with a harness-only device-error domain.
    bodies = source[source.index('static GError *'):]
    harness = (ROOT / 'tests/tls-safety-harness.c').read_text()
    return source[:source.index('#include')] + harness.replace(
        '/* INSERT SERVER TYPES */', types).replace('/* INSERT TLS IMPLEMENTATION */', bodies)


FLOW_CASES = ('deadline-request', 'deadline-local-read', 'cancel-proxy',
              'old-usb-generation', 'usb-error-stops', 'command-timeout',
              'image-fragments', 'image-timeout', 'image-send-error', 'core-cancel-tls', 'core-cancel-image', 'abort-request', 'abort-local-read', 'abort-image', 'image-oversize')


def flow_unit():
    spec = importlib.util.spec_from_file_location('flow_runner', ROOT / 'scripts/07-test-tls-flow.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.FIXED = SOURCE.parents[2]
    module.FUNCTIONS = (*module.FUNCTIONS, 'goodix_tls_socket_poll',
                       'goodix_receive_data_cb', 'goodix_receive_timeout_cb',
                       'goodix_image_finish', 'goodix_image_poll',
                       'goodix_tls_ready_image_handler', 'goodix_abort_operation')
    result = module.generated_unit()
    result = result.replace('#include <gio/gio.h>', '#include <gio/gio.h>\n#include <errno.h>')
    result = result.replace('#define GOODIX_TIMEOUT 1000', '#define GOODIX_TIMEOUT 1000\n#define GOODIX_TLS_DEADLINE_MS 15000\n#define GOODIX_CAPTURE_IMAGE_BYTES 14260')
    result = result.replace('typedef struct _FpiSsm FpiSsm;',
                            'typedef struct _FpiSsm FpiSsm;\ntypedef struct {guint8 *buffer; guint actual_length;} FpiUsbTransfer;')
    result = result.replace('static void goodix_tls_poll (FpDevice *, gpointer);',
                            'static void goodix_tls_poll (FpDevice *, gpointer);\nstatic void tls_handshake_run (FpiSsm *, FpDevice *);\nstatic void goodix_image_finish (FpDevice *, GError *);\nstatic void goodix_tls_socket_poll(FpDevice *,gpointer);\nvoid goodix_receive_timeout_cb(FpDevice *,gpointer);')
    before = 'static void\nrespond (FpDevice *dev, GError *error)'
    # The inserted real functions need these transport/scheduler stand-ins.
    marker = '/* A one-shot device timeout is rescheduled'
    extra = """
static GCancellable *fpi_device_get_cancellable(FpDevice *dev) { return dev->core_cancel; }
static void fpi_ssm_next_state_delayed(FpiSsm *ssm, guint ms) { fpi_ssm_next_state(ssm); }
static void goodix_receive_pack(FpDevice *dev, guint8 *data, guint32 length) { g_assert_not_reached(); }
static int goodix_tls_server_receive(GoodixTlsServer *server, guint8 *data, guint32 length, GError **error)
{ FpDevice *dev=server->user_data; guint count=MIN(MIN(length,6000),14260-dev->priv.image_length); if(dev->read_result==14261) count=length; memset(data,0x42,count); return count; }
"""
    result = result.replace('void\ngoodix_receive_done (', extra + '\nvoid\ngoodix_receive_done (', 1)
    result = result.replace('g_assert_true (callback == goodix_tls_poll);', '(void)callback;')
    result = result.replace('return dev->read_result;', ' { if (dev->read_result < 0) errno = EAGAIN; return dev->read_result; }')
    result = result.replace('  Result tls, image, activation;', '  Result tls, image, activation;\n  GCancellable *core_cancel;')
    result = result.replace('  dev.sources = g_ptr_array_new_with_free_func',
                            '  dev.priv.transfer_cancel_tkn = g_cancellable_new();\n  dev.core_cancel=g_cancellable_new();\n  dev.sources = g_ptr_array_new_with_free_func')
    result = result.replace('  g_ptr_array_unref (dev->sources);',
                            '  g_ptr_array_unref (dev->sources);\n  g_clear_object(&dev->priv.transfer_cancel_tkn);\n  g_clear_object(&dev->core_cancel);')
    cases = """
  if (!strcmp(name,"abort-request") || !strcmp(name,"abort-local-read"))
    {if (!strcmp(name,"abort-local-read")){dev.fail_read_at=1;dev.read_result=-1;}
     start_tls(&dev);if(!strcmp(name,"abort-local-read"))respond(&dev,NULL);
     goodix_abort_operation(&dev);expect_tls_error(&dev,FALSE);
     g_assert_false(g_cancellable_is_cancelled(dev.priv.transfer_cancel_tkn));}
  else if (!strcmp(name,"core-cancel-tls"))
    {start_tls(&dev); g_cancellable_cancel(dev.core_cancel);poll_once(&dev);expect_tls_error(&dev,FALSE);}
  else if (!strcmp(name,"deadline-request") || !strcmp(name,"deadline-local-read") || !strcmp(name,"cancel-proxy"))
    {
      if (!strcmp(name,"deadline-local-read")) {dev.fail_read_at=1; dev.read_result=-1;}
      start_tls(&dev);
      if (strcmp(name,"deadline-request")) respond(&dev,NULL);
      if (!strcmp(name,"cancel-proxy")) g_cancellable_cancel(dev.priv.transfer_cancel_tkn);
      else dev.priv.tls_deadline=g_get_monotonic_time()-1;
      poll_once(&dev); expect_tls_error(&dev,FALSE);
      g_assert_null(dev.priv.tls_socket_poll);
    }
  else if (!strcmp(name,"old-usb-generation") || !strcmp(name,"usb-error-stops"))
    {
      start_tls(&dev); dev.priv.inited=TRUE; dev.priv.read_generation=10;
      guint reads=dev.reads; FpiUsbTransfer transfer={0};
      goodix_receive_data_cb(&transfer,&dev,GUINT_TO_POINTER(9),injected_error());
      g_assert_cmpuint(dev.tls.calls,==,0); g_assert_cmpuint(dev.reads,==,reads+1);
      if (!strcmp(name,"usb-error-stops"))
        {goodix_receive_data_cb(&transfer,&dev,GUINT_TO_POINTER(10),injected_error());
         expect_tls_error(&dev,TRUE);g_assert_cmpuint(dev.reads,==,reads+1);}
      else {respond(&dev,injected_error());expect_tls_error(&dev,TRUE);}
    }
  else if (!strcmp(name,"command-timeout"))
    {start_tls(&dev);goodix_receive_timeout_cb(&dev,NULL);expect_tls_error(&dev,TRUE);}
  else if (g_str_has_prefix(name,"image-") || !strcmp(name,"core-cancel-image") || !strcmp(name,"abort-image"))
    {
      start_tls(&dev); finish_success(&dev);
      GoodixCallbackInfo *info=g_new0(GoodixCallbackInfo,1);
      info->callback=G_CALLBACK(image_result);info->user_data=&dev.image;
      guint8 data[10]={0};
      if (!strcmp(name,"image-send-error")){dev.fail_send_at=dev.local_sends+1;dev.send_result=-1;}
      if(!strcmp(name,"image-oversize"))dev.read_result=14261;
      goodix_tls_ready_image_handler(&dev,data,sizeof data,info,NULL);
      if(!strcmp(name,"abort-image"))goodix_abort_operation(&dev);
      if (!strcmp(name,"core-cancel-image")) g_cancellable_cancel(dev.core_cancel);
      if (!strcmp(name,"image-timeout")) dev.priv.image_deadline=g_get_monotonic_time()-1;
      while(dev.priv.image_callback)
        {g_assert_nonnull(dev.priv.image_poll);g_source_destroy(dev.priv.image_poll);goodix_image_poll(&dev,NULL);}
      g_assert_cmpuint(dev.image.calls,==,1);
      g_assert_cmpuint(dev.image.successes,==,!strcmp(name,"image-fragments"));
      g_assert_cmpuint(dev.image.failures,==,strcmp(name,"image-fragments")!=0);
      g_assert_null(dev.priv.image_buffer);g_assert_null(dev.priv.image_poll);
    }
  else
"""
    return result.replace('  if (!strcmp (name, "retry-budget"))', cases + '  if (!strcmp (name, "retry-budget"))')


COMMAND_CASES = ('nop-success', 'nop-send-error', 'nop-no-callback-error',
                 'nop-busy', 'protocol-busy-callback', 'protocol-busy-no-callback')


def command_unit():
    spec = importlib.util.spec_from_file_location('command_runner', ROOT / 'scripts/07-test-tls-flow.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = (SOURCE / 'goodix.c').read_text()
    protocol = (SOURCE / 'goodix_proto.c').read_text()
    header = (SOURCE / 'goodix_proto.h').read_text()
    result = flow_unit()
    # Replace only this unit's synthetic send path with the real command bodies.
    fixture = module.function(result, 'goodix_send_protocol')
    result = result.replace(fixture, 'void goodix_send_protocol(FpDevice *, guint8, guint8 *, guint16, GDestroyNotify, gboolean, guint, gboolean, GoodixCmdCallback, gpointer);')
    definitions = []
    for name in ('GoodixNop', 'GoodixProtocol'):
        start = header.index('typedef struct __attribute__((__packed__)) _' + name)
        end = header.index('} ' + name + ';', start) + len('} ' + name + ';')
        definitions.append(header[start:end])
    start = protocol.index('guint8\ngoodix_calc_checksum')
    end = protocol.index('\n}', start) + 2
    definitions.append(protocol[start:end])
    definitions.append(module.function(protocol, 'goodix_encode_protocol'))
    definitions.append(module.function(source, 'goodix_send_nop'))
    definitions.append(module.function(source, 'goodix_send_protocol'))
    definitions.append('static void busy_result(FpDevice *dev, guint8 *data, guint16 length, gpointer unused, GError *error) {record_result(&dev->activation,error);}')
    result = result.replace('void\ngoodix_receive_done (', '\n'.join(definitions) + '\nvoid\ngoodix_receive_done (', 1)
    result = result.replace('#define GOODIX_TIMEOUT 1000', '#define GOODIX_TIMEOUT 1000\n#define GOODIX_CMD_NOP 0x00\n#define GOODIX_CMD_MCU_SWITCH_TO_FDT_DOWN 0x32\n#define GOODIX_CMD_MCU_SWITCH_TO_FDT_UP 0x34\n#define GOODIX_FLAGS_MSG_PROTOCOL 0xa0\n#define GOODIX_NULL_CHECKSUM 0xff\n#define GOODIX_EP_OUT_MAX_BUF_SIZE 64')
    result = result.replace('  g_assert_cmpuint (flags, ==, GOODIX_FLAGS_TLS);', '  g_assert_true(flags == GOODIX_FLAGS_TLS || flags == GOODIX_FLAGS_MSG_PROTOCOL);')
    result = result.replace('  g_assert_cmpuint (length, ==, 4);', """
  if(flags == GOODIX_FLAGS_MSG_PROTOCOL)
    {
      const guint8 expected[]={0,5,0,0,0,0,0,255};
      g_assert_cmpuint(length,==,sizeof expected);
      g_assert_cmpmem(payload,length,expected,sizeof expected);
      if(free_func)free_func(payload);
    }
  else g_assert_cmpuint (length, ==, 4);
""", 1)
    cases = """
  if (g_str_has_prefix(name,"nop-") && strcmp(name,"nop-busy"))
    {
      gboolean failed=strcmp(name,"nop-success")!=0;
      if(failed)dev.fail_pack_at=1;
      guint generation=dev.priv.read_generation;
      goodix_send_nop(&dev,!strcmp(name,"nop-no-callback-error")?NULL:tls_result,&dev.tls);
      g_assert_cmpuint(dev.reads,==,0);g_assert_cmpuint(dev.packs,==,1);
      g_assert_cmpuint(dev.sources->len,==,0);g_assert_null(dev.priv.timeout);
      g_assert_cmpuint(dev.priv.read_generation,==,generation);
      g_assert_false(dev.priv.ack||dev.priv.reply);g_assert_null(dev.priv.callback);
      g_assert_cmpuint(dev.tls.calls,==,strcmp(name,"nop-no-callback-error")!=0);
      if(dev.tls.calls)g_assert_cmpuint(dev.tls.failures,==,failed);
    }
  else if(!strcmp(name,"nop-busy")||g_str_has_prefix(name,"protocol-busy-"))
    {
      GoodixCallbackInfo *old=g_new0(GoodixCallbackInfo,1);
      old->callback=G_CALLBACK(image_result);old->user_data=&dev.image;
      dev.priv.cmd=0xa8;dev.priv.ack=TRUE;dev.priv.reply=TRUE;
      dev.priv.callback=goodix_receive_default;dev.priv.user_data=old;
      dev.priv.timeout=fpi_device_add_timeout(&dev,1000,goodix_receive_timeout_cb,NULL,NULL);
      GSource *timeout=dev.priv.timeout;guint generation=dev.priv.read_generation;
      if(!strcmp(name,"nop-busy"))goodix_send_nop(&dev,tls_result,&dev.tls);
      else goodix_send_protocol(&dev,0xe4,g_malloc0(4),4,g_free,TRUE,1000,TRUE,
        !strcmp(name,"protocol-busy-no-callback")?NULL:busy_result,NULL);
      GError *error=!strcmp(name,"nop-busy")?dev.tls.error:dev.activation.error;
      if(strcmp(name,"protocol-busy-no-callback"))g_assert_error(error,G_IO_ERROR,G_IO_ERROR_BUSY);
      else g_assert_cmpuint(dev.activation.calls,==,0);
      g_assert_cmpuint(dev.packs,==,0);g_assert_cmpuint(dev.reads,==,0);
      g_assert_true(dev.priv.ack&&dev.priv.reply);g_assert_cmpuint(dev.priv.cmd,==,0xa8);
      g_assert_true(dev.priv.callback==goodix_receive_default);g_assert_true(dev.priv.user_data==old);
      g_assert_true(dev.priv.timeout==timeout);g_assert_cmpuint(dev.priv.read_generation,==,generation);
      respond(&dev,NULL);g_assert_cmpuint(dev.image.calls,==,1);g_assert_cmpuint(dev.image.successes,==,1);
    }
  else
"""
    return result.replace('  if (!strcmp(name,"abort-request")', cases + '  if (!strcmp(name,"abort-request")')


def run():
    if os.geteuid() == 0 or not Path(sys.executable).resolve().is_relative_to('/nix/store'):
        raise RuntimeError('Run with existing Nix Python as the regular user, without sudo')
    check_inputs()
    flags = shlex.split(subprocess.check_output(
        ['pkg-config', '--cflags', '--libs', 'gio-2.0', 'openssl'], text=True, timeout=10))
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',
               UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    def no_core():
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    with tempfile.TemporaryDirectory(prefix='tls-safety-', dir=ROOT / 'work') as directory:
        c = Path(directory) / 'safety.c'
        binary = Path(directory) / 'safety'
        c.write_text(unit())
        subprocess.run(['cc', '-std=c11', '-g', '-O1', '-Wall', '-Wextra',
                        '-Wno-unused-parameter', '-Werror=implicit-function-declaration',
                        '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-pthread',
                        str(c), '-o', str(binary), *flags], check=True, timeout=60)
        for case in CASES:
            subprocess.run([str(binary), case], check=True, timeout=10, env=env,
                           preexec_fn=no_core)
            print('PASS:', case, flush=True)
        c.write_text(flow_unit())
        subprocess.run(['cc', '-std=c11', '-g', '-O1', '-Wall', '-Wextra',
                        '-Wno-unused-parameter', '-Werror=implicit-function-declaration',
                        '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-pthread',
                        str(c), '-o', str(binary), *flags], check=True, timeout=60)
        spec = importlib.util.spec_from_file_location('flow_cases', ROOT / 'scripts/07-test-tls-flow.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for case in (*FLOW_CASES, *module.CASES):
            subprocess.run([str(binary), case], check=True, timeout=10, env=env,
                           preexec_fn=no_core)
            print('PASS:', case, flush=True)
        c.write_text(command_unit())
        subprocess.run(['cc', '-std=c11', '-g', '-O1', '-Wall', '-Wextra',
                        '-Wno-unused-parameter', '-Werror=implicit-function-declaration',
                        '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-pthread',
                        str(c), '-o', str(binary), *flags], check=True, timeout=60)
        for case in COMMAND_CASES:
            subprocess.run([str(binary), case], check=True, timeout=10, env=env,
                           preexec_fn=no_core)
            print('PASS:', case, flush=True)
    subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/helpers/test-device-safety.py')],
                   check=True, timeout=90)
    check_inputs()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--run', action='store_true')
    modes.add_argument('--plan', action='store_true')
    modes.add_argument('--check-inputs', action='store_true')
    args = parser.parse_args()
    if args.check_inputs:
        try:
            check_inputs()
            print('Reviewed source/patch inputs match; no compilation, TLS or USB run.')
            return 0
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            print('Check failed:', error, file=sys.stderr)
            return 1
    if not args.run:
        print('Offline only: compile actual TLS functions with acquisition fault shims;')
        print('run real PSK TLS1.2/socket fragmentation, partial init, silent-peer timeout,')
        print('and repeated stop/join with ASan/UBSan. No USB or network sockets are opened.')
        return 0
    try:
        run()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print('Check failed:', error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
