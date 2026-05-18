# -*- coding: utf-8 -*-
"""
Logging module for Computer Room Management System
Provides centralized logging for all components
"""

import logging
import os
from datetime import datetime
from pathlib import Path

# Create logs directory
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

# Configure log file path
LOG_FILE = LOGS_DIR / f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

class LoggerSetup:
    """
    Setup and configure logging for the application
    """
    
    _loggers = {}
    
    @staticmethod
    def get_logger(name, level=logging.DEBUG):
        """
        Get or create a logger instance
        
        Args:
            name (str): Logger name (usually __name__)
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            
        Returns:
            logging.Logger: Configured logger instance
        """
        
        if name in LoggerSetup._loggers:
            return LoggerSetup._loggers[name]
        
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # Prevent duplicate handlers
        if logger.hasHandlers():
            return logger
        
        # Create formatters
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # File handler
        try:
            file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Failed to create file handler: {e}")
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(levelname)s - %(name)s: %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        LoggerSetup._loggers[name] = logger
        return logger


# Create a default logger
logger = LoggerSetup.get_logger("app")


def log_exception(logger_obj, exception, context=""):
    """
    Log an exception with context information
    
    Args:
        logger_obj: Logger instance
        exception: Exception object
        context: Context string describing where error occurred
    """
    logger_obj.error(
        f"Exception in {context}: {type(exception).__name__}: {str(exception)}",
        exc_info=True
    )
