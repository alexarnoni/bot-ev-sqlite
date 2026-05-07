#!/usr/bin/env python3
"""Entrypoint wrapper - delegates to src.scanner.main_scheduler"""
import sys
import os

# Ensure project root is in sys.path for src package resolution
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.scanner.main_scheduler import main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
