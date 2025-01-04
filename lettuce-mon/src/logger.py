from enum import IntEnum
from datetime import datetime
import os
import sys
# Fixed multi-threading bug by using os.write instead of print
# Ref: https://stackoverflow.com/questions/75367828/runtimeerror-reentrant-call-inside-io-bufferedwriter-name-stdout

'''
Ref: https://stackoverflow.com/questions/2031163/when-to-use-the-different-log-levels
Trace - Only when I would be "tracing" the code and trying to find one part of a function specifically.
Debug - Information that is diagnostically helpful to people more than just developers (IT, sysadmins, etc.).
Info - Generally useful information to log (service start/stop, configuration assumptions, etc). Info I want to always have available but usually don't care about under normal circumstances. This is my out-of-the-box config level.
Warn - Anything that can potentially cause application oddities, but for which I am automatically recovering. (Such as switching from a primary to backup server, retrying an operation, missing secondary data, etc.)
Error - Any error which is fatal to the operation, but not the service or application (can't open a required file, missing data, etc.). These errors will force user (administrator, or direct user) intervention. These are usually reserved (in my apps) for incorrect connection strings, missing services, etc.
Fatal - Any error that is forcing a shutdown of the service or application to prevent data loss (or further data loss). I reserve these only for the most heinous errors and situations where there is guaranteed to have been data corruption or loss.
'''

class MessageLevel(IntEnum):
    TRACE = 0
    DEBUG = 1
    INFO = 2
    WARN = 3
    ERROR = 4
    FATAL = 5

class Logger:
    
    '''
    Create a logger object with a specific log level and mute list.
    '''
    def __init__(self, 
                 log_level = MessageLevel.INFO, 
                 mute_keys = []) -> None:
        self._msg_count = 0
        self.log_level = log_level
        self._mute_list = []
        #self._mute_list.append("h2music")
        #self._mute_list.append("audio_driver")
        self._mute_list.append("md2a_model")
        self._mute_list.append(mute_keys)
        pass

    '''
    Write a message to the log.
    '''
    def write(self, key, msg, level = MessageLevel.INFO) -> None:
        # Step 0 - Short-circuit if the message is muted
        if (key in self._mute_list):
            return
        if (level < self.log_level):
            return
        # Step 1 - Write the message
        level_str = ""
        if (level == MessageLevel.TRACE):
            level_str = 'TRACE'
        elif (level == MessageLevel.DEBUG):
            level_str = 'DEBUG'
        elif (level == MessageLevel.INFO):
            level_str = 'INFO'
        elif (level == MessageLevel.WARN):
            level_str = 'WARN'
        elif (level == MessageLevel.ERROR):
            level_str = 'ERROR'
        elif (level == MessageLevel.FATAL):
            level_str = 'FATAL'
        else:
            level_str = 'UNKNOWN'
        # Format
        # [DateTime][key][level]{message} 
        header = "[{0}][{1}][{2}]".format(datetime.now(),
                                            key,
                                            level_str).ljust(60)
        #print(header + msg)
        os.write(sys.stdout.fileno(), (header + msg + "\n").encode('utf8'))