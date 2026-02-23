import time
from pathlib import Path
from Foundation import NSURL, NSRunLoop, NSDate, NSLocale
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

# Native Speech Recognition (macOS)
try:
    from Speech import (
        SFSpeechRecognizer,
        SFSpeechURLRecognitionRequest,
        SFSpeechRecognizerAuthorizationStatusAuthorized,
    )
except ImportError:
    SFSpeechRecognizer = None

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


def _request_speech_auth(timeout=5.0):
    if not SFSpeechRecognizer:
        return False, "Speech framework not available"
    status_holder = {"done": False, "status": None}

    def handler(status):
        status_holder["done"] = True
        status_holder["status"] = status

    SFSpeechRecognizer.requestAuthorization_(handler)
    loop = NSRunLoop.currentRunLoop()
    end_time = time.time() + timeout
    while time.time() < end_time and not status_holder["done"]:
        loop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))

    if not status_holder["done"]:
        return False, "Speech authorization timed out"
    if status_holder["status"] != SFSpeechRecognizerAuthorizationStatusAuthorized:
        return False, "Speech recognition not authorized"
    return True, None


def transcribe_audio_native(audio_path: Path, locale="en-US"):
    """Transcribes audio using macOS Speech framework."""
    if not SFSpeechRecognizer:
        return None, "Speech framework not available"

    ok, err = _request_speech_auth()
    if not ok:
        return None, err

    try:
        locale_obj = NSLocale.alloc().initWithLocaleIdentifier_(locale)
        recognizer = SFSpeechRecognizer.alloc().initWithLocale_(locale_obj)
        request = SFSpeechURLRecognitionRequest.alloc().initWithURL_(
            NSURL.fileURLWithPath_(str(audio_path))
        )

        result_holder = {"done": False, "text": None, "err": None}

        def handler(result, error):
            if error is not None:
                result_holder["err"] = str(error)
                result_holder["done"] = True
                return
            if result is not None:
                result_holder["text"] = str(result.bestTranscription().formattedString())
                if result.isFinal():
                    result_holder["done"] = True

        recognizer.recognitionTaskWithRequest_resultHandler_(request, handler)

        loop = NSRunLoop.currentRunLoop()
        end_time = time.time() + 30.0
        while time.time() < end_time and not result_holder["done"]:
            loop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))

        if result_holder["err"]:
            return None, result_holder["err"]
        return result_holder["text"], None
    except Exception as e:
        return None, f"Native speech error: {e}"


def quick_voice_input(duration=5, engine="native"):
    """Native recording + native speech-to-text (fallback to Google if needed)."""
    # Use WAV for the temporary file for easiest processing
    tmp_path = Path("/tmp/openss_voice.wav")
    if tmp_path.exists():
        tmp_path.unlink()
        
    success, err = record_audio_native(tmp_path, duration)
    if not success:
        return None, err

    text, err = (None, None)
    if engine == "native":
        text, err = transcribe_audio_native(tmp_path)
        if err:
            text = None
    if engine != "native" or text is None:
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
