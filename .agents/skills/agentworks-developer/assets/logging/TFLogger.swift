import Foundation

/// 仅在定义 DEBUG 的构建中输出业务日志；没有全局可变配置。
public enum TFLog {
    /// 五个等级均默认输出，等级只描述严重程度，不触发崩溃或上报。
    public enum Level: String {
        case debug = "DEBUG"
        case info = "INFO"
        case warning = "WARNING"
        case error = "ERROR"
        case fault = "FAULT"
    }

    /// 延迟生成消息，Release 下不会执行插值、函数调用或其他消息表达式。
    public static func log(
        _ level: Level, _ message: @autoclosure () -> String,
        file: StaticString = #fileID, function: StaticString = #function, line: UInt = #line
    ) {
        #if DEBUG
        // 使用固定格式串，避免把消息中的百分号当成格式指令。
        NSLog("%@", "[TFLog][\(level.rawValue)] [\(file):\(line) \(function)] \(message())")
        #endif
    }

    /// 输出开发排错信息，自动保留实际调用位置。
    public static func debug(_ message: @autoclosure () -> String, file: StaticString = #fileID,
                             function: StaticString = #function, line: UInt = #line) {
        log(.debug, message(), file: file, function: function, line: line)
    }

    /// 输出正常业务过程中的重要信息。
    public static func info(_ message: @autoclosure () -> String, file: StaticString = #fileID,
                            function: StaticString = #function, line: UInt = #line) {
        log(.info, message(), file: file, function: function, line: line)
    }

    /// 输出可恢复的异常情况。
    public static func warning(_ message: @autoclosure () -> String, file: StaticString = #fileID,
                               function: StaticString = #function, line: UInt = #line) {
        log(.warning, message(), file: file, function: function, line: line)
    }

    /// 输出操作失败的信息，不替代业务错误处理。
    public static func error(_ message: @autoclosure () -> String, file: StaticString = #fileID,
                             function: StaticString = #function, line: UInt = #line) {
        log(.error, message(), file: file, function: function, line: line)
    }

    /// 输出严重异常信息；本方法不会终止进程。
    public static func fault(_ message: @autoclosure () -> String, file: StaticString = #fileID,
                             function: StaticString = #function, line: UInt = #line) {
        log(.fault, message(), file: file, function: function, line: line)
    }
}
