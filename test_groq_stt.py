from groq.types.audio import Transcription
t = Transcription(text="hello world")
print(str(t))
print(t.text)
