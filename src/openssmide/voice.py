import os
import time
from pathlib import Path
from Foundation import NSURL, NSRunLoop, NSDate
import objc
import speech_recognition as sr

# Native AVFoundation for "Bare Metal" Recording
try:
    from AVFoundation import (
        AVAudioSession,
        AVAudioSessionCategoryPlayAndRecord,
        AVAudioRecorder,
        AVFormatIDKey,
        kAudioFormatLinearPCM, # Switching to PCM for easier compatibility with SpeechRecognition
        AVNumberOfChannelsKey,
        AVSampleRateKey,
        AVLinearPCMBitDepthKey,
        AVLinearPCMIsBigEndianKey,
        AVLinearPCMIsFloatKey,
    )
except ImportError:
    AVAudioSession = None

def record_audio_native(output_path: Path, duration=5):
    """Records audio using native macOS AVFoundation (Bare Metal approach)."""
    if not AVAudioSession:
        return False, "macOS AVFoundation not available"
        
    try:
        session = AVAudioSession.sharedInstance()
        session.setCategory_error_(AVAudioSessionCategoryPlayAndRecord, None)
        session.setActive_error_(True, None)

        # Using WAV-style PCM settings for direct compatibility
        settings = {
            AVFormatIDKey: kAudioFormatLinearPCM,
            AVSampleRateKey: 44100.0,
            AVNumberOfChannelsKey: 1,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsBigEndianKey: False,
            AVLinearPCMIsFloatKey: False,
        }
        url = NSURL.fileURLWithPath_(str(output_path))
        recorder, err = AVAudioRecorder.alloc().initWithURL_settings_error_(url, settings, None)
        
        if err:
            return False, f"Failed to init recorder: {err}"

        if not recorder.prepareToRecord():
            return False, "Recorder failed to prepare"

        recorder.recordForDuration_(duration)
        
        # Wait for recording to finish using the native run loop
        loop = NSRunLoop.currentRunLoop()
        end_time = time.time() + duration + 0.3
        while time.time() < end_time:
            loop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
            
        recorder.stop()
        return True, None
    except Exception as e:
        return False, f"Native recording error: {e}"

def transcribe_audio_google(audio_path: Path):
    """Transcribes an audio file using Google Speech Recognition (Fast, Free, No TCC Crash)."""
    r = sr.Recognizer()
    try:
        with sr.AudioFile(str(audio_path)) as source:
            audio_data = r.record(source)
            # recognize (convert from speech to text)
            text = r.recognize_google(audio_data)
            return text, None
    except sr.UnknownValueError:
        return None, "Speech was unintelligible"
    except sr.RequestError as e:
        return None, f"Could not request results from Google Speech Recognition service; {e}"
    except Exception as e:
        return None, f"Transcription error: {e}"

def quick_voice_input(duration=5):
    """Hybrid: Native 'Bare Metal' recording + Fast Google Transcription."""
    # Use WAV for the temporary file for easiest processing
    tmp_path = Path("/tmp/openss_voice.wav")
    if tmp_path.exists():
        tmp_path.unlink()
        
    success, err = record_audio_native(tmp_path, duration)
    if not success:
        return None, err
        
    text, err = transcribe_audio_google(tmp_path)
    
    # Cleanup
    if tmp_path.exists():
        tmp_path.unlink()
        
    return text, err

if __name__ == "__main__":
    print(f"Testing Native Recording + Google Transcription ({5}s)...")
    print("Please speak now...")
    txt, err = quick_voice_input(5)
    if err:
        print(f"\nError: {err}")
    else:
        print(f"\nResult: {txt}")
