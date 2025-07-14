#!/usr/bin/env python3
"""
Test script for Gemini Video Voiceover Translator
"""

import os
import sys
from pathlib import Path

def test_file_structure():
    """Test if all required files exist"""
    required_files = [
        'app.py',
        'config.py',
        'requirements.txt',
        '.env.example',
        'README.md',
        'modules/gemini_client.py',
        'modules/video_processor.py',
        'modules/file_manager.py',
        'templates/index.html',
        'static/css/style.css',
        'static/js/app.js'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print("❌ Missing files:")
        for file in missing_files:
            print(f"   - {file}")
        return False
    else:
        print("✅ All required files exist")
        return True

def test_imports():
    """Test if all modules can be imported"""
    try:
        from config import Config
        print("✅ Config module imported successfully")
        
        from modules.gemini_client import GeminiClient
        print("✅ GeminiClient module imported successfully")
        
        from modules.video_processor import VideoProcessor
        print("✅ VideoProcessor module imported successfully")
        
        from modules.file_manager import FileManager
        print("✅ FileManager module imported successfully")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_dependencies():
    """Test if all dependencies are available"""
    dependencies = [
        'flask',
        'python-dotenv',
        'google.genai',
        'ffmpeg',
        'werkzeug'
    ]
    
    missing_deps = []
    for dep in dependencies:
        try:
            if dep == 'python-dotenv':
                import dotenv
            elif dep == 'google.genai':
                import google.genai
            else:
                __import__(dep)
            print(f"✅ {dep} is available")
        except ImportError:
            missing_deps.append(dep)
            print(f"❌ {dep} is missing")
    
    return len(missing_deps) == 0

def test_configuration():
    """Test configuration loading"""
    try:
        from config import Config
        
        # Test basic configuration
        print(f"✅ Supported languages: {Config.SUPPORTED_LANGUAGES}")
        print(f"✅ Available voices: {Config.AVAILABLE_VOICES}")
        print(f"✅ Allowed extensions: {Config.ALLOWED_VIDEO_EXTENSIONS}")
        
        # Test directory creation
        Config.validate_config()
        print("✅ Configuration validation passed")
        
        return True
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing Gemini Video Voiceover Translator")
    print("=" * 50)
    
    tests = [
        ("File Structure", test_file_structure),
        ("Dependencies", test_dependencies),
        ("Module Imports", test_imports),
        ("Configuration", test_configuration)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Testing {test_name}:")
        result = test_func()
        results.append(result)
    
    print("\n" + "=" * 50)
    if all(results):
        print("🎉 All tests passed! The application is ready to run.")
        print("\nNext steps:")
        print("1. Copy .env.example to .env")
        print("2. Add your GEMINI_API_KEY to the .env file")
        print("3. Run: python app.py")
        print("4. Open http://localhost:5000 in your browser")
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
