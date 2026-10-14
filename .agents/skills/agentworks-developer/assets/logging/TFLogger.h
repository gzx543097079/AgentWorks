#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

/// 五个日志等级均在 Debug 默认输出，Fault 不触发崩溃或远程上报。
typedef NS_ENUM(NSInteger, TFLogLevel) {
    TFLogLevelDebug,
    TFLogLevelInfo,
    TFLogLevelWarning,
    TFLogLevelError,
    TFLogLevelFault
};

#if defined(DEBUG) && DEBUG
/// 宏的内部输出入口；业务代码使用下方宏以保证 Release 不计算日志参数。
FOUNDATION_EXPORT void TFLogWrite(TFLogLevel level, const char *file, const char *function,
                                 NSUInteger line, NSString *format, ...) NS_FORMAT_FUNCTION(5, 6);

/// 在调用点捕获位置；宏作为单条语句使用，不改变外部 if/else 结构。
#define TFLLog(level, ...) do { TFLogWrite((level), __FILE__, __PRETTY_FUNCTION__, __LINE__, __VA_ARGS__); } while (0)
#else
// Release 直接移除整次调用，包括等级、格式串和所有参数的求值。
#define TFLLog(level, ...) do { } while (0)
#endif

/// 记录开发排错信息。
#define TFLDebug(...) TFLLog(TFLogLevelDebug, __VA_ARGS__)
/// 记录正常业务过程中的重要信息。
#define TFLInfo(...) TFLLog(TFLogLevelInfo, __VA_ARGS__)
/// 记录可恢复异常。
#define TFLWarning(...) TFLLog(TFLogLevelWarning, __VA_ARGS__)
/// 记录操作失败，不替代 NSError 或回调处理。
#define TFLError(...) TFLLog(TFLogLevelError, __VA_ARGS__)
/// 记录严重异常，不终止进程。
#define TFLFault(...) TFLLog(TFLogLevelFault, __VA_ARGS__)

NS_ASSUME_NONNULL_END
