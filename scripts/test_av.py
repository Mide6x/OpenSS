from AVFoundation import AVAudioSession, AVAudioSessionCategoryPlayAndRecord
print("Testing AVAudioSession...")
session = AVAudioSession.sharedInstance()
session.setCategory_error_(AVAudioSessionCategoryPlayAndRecord, None)
print("Set category success")
session.setActive_error_(True, None)
print("Set active success")
