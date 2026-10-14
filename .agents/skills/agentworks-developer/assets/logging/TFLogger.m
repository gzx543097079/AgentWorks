#import "TFLogger.h"

#if defined(DEBUG) && DEBUG
/// 无共享可变状态；每条日志组装完后交给 Foundation 输出。
void TFLogWrite(TFLogLevel level, const char *file, const char *function,
                NSUInteger line, NSString *format, ...) {
    @autoreleasepool {
        NSString *label;
        switch (level) {
            case TFLogLevelDebug: label = @"DEBUG"; break;
            case TFLogLevelInfo: label = @"INFO"; break;
            case TFLogLevelWarning: label = @"WARNING"; break;
            case TFLogLevelError: label = @"ERROR"; break;
            case TFLogLevelFault: label = @"FAULT"; break;
            default: label = @"UNKNOWN"; break;
        }
        va_list arguments;
        va_start(arguments, format);
        NSString *message = [[NSString alloc] initWithFormat:format arguments:arguments];
        va_end(arguments);
        // 仅输出源文件名，避免携带开发机器上的完整路径。
        NSString *filename = [@(file) lastPathComponent];
        NSLog(@"[TFLog][%@] [%@:%lu %s] %@", label, filename, (unsigned long)line, function, message);
    }
}
#endif
