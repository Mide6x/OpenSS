from Speech import SFSpeechRecognizer
from Foundation import NSLocale
print("Testing SFSpeechRecognizer...")
locale = NSLocale.alloc().initWithLocaleIdentifier_("en-US")
recognizer = SFSpeechRecognizer.alloc().initWithLocale_(locale)
print(f"Recognizer created: {recognizer}")
print(f"Available: {recognizer.isAvailable()}")
