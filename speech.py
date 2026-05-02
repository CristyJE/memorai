"""
services/speech.py

Azure AI Speech wrapper — handles both Speech-to-Text (STT)
and Text-to-Speech (TTS), tuned for elderly Filipino speakers.
"""

import os
import azure.cognitiveservices.speech as speechsdk


class SpeechService:
    """
    Wraps Azure AI Speech SDK for MemorAI interview sessions.
    Configured for slower cadence, Filipino/Philippine English accents,
    and a warm TTS voice persona.
    """

    # Azure Neural Voice — warm, unhurried Philippine English
    DEFAULT_VOICE = "en-PH-RosaNeural"
    FILIPINO_VOICE = "fil-PH-BlessicaNeural"

    def __init__(self):
        self.speech_key = os.environ["AZURE_SPEECH_KEY"]
        self.speech_region = os.environ["AZURE_SPEECH_REGION"]

        self.speech_config = speechsdk.SpeechConfig(
            subscription=self.speech_key,
            region=self.speech_region,
        )

        # STT: accept Philippine English and Filipino
        self.speech_config.speech_recognition_language = "en-PH"

        # TTS: use warm Philippine English Neural Voice
        self.speech_config.speech_synthesis_voice_name = self.DEFAULT_VOICE

        # Increase recognition timeout for elderly speakers (longer pauses)
        self.speech_config.set_property(
            speechsdk.PropertyId.SpeechServiceConnection_InitialSilenceTimeoutMs,
            "10000",  # 10 seconds
        )
        self.speech_config.set_property(
            speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs,
            "3000",  # 3 seconds — allows natural pauses mid-sentence
        )

    def transcribe_audio(self, audio_file_path: str) -> dict:
        """
        Transcribe a recorded audio file to text.

        Args:
            audio_file_path: Path to WAV/MP3 audio file.

        Returns:
            dict with 'text', 'confidence', and 'duration_seconds'.
        """
        audio_config = speechsdk.AudioConfig(filename=audio_file_path)
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=self.speech_config,
            audio_config=audio_config,
        )

        result = recognizer.recognize_once_async().get()

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            return {
                "text": result.text,
                "confidence": result.properties.get(
                    speechsdk.PropertyId.SpeechServiceResponse_JsonResult, "{}"
                ),
                "duration_seconds": result.duration / 10_000_000,  # ticks to seconds
                "success": True,
            }
        elif result.reason == speechsdk.ResultReason.NoMatch:
            return {"text": "", "success": False, "error": "No speech detected"}
        else:
            return {
                "text": "",
                "success": False,
                "error": str(result.cancellation_details.error_details),
            }

    def synthesize_speech(
        self,
        text: str,
        output_path: str,
        voice: str = DEFAULT_VOICE,
        rate: str = "-15%",  # Slightly slower for elderly listeners
    ) -> bool:
        """
        Convert agent text response to speech audio file.

        Args:
            text: The text to synthesize.
            output_path: Where to save the output WAV file.
            voice: Azure Neural Voice name.
            rate: Speaking rate adjustment (e.g. '-15%' for slower).

        Returns:
            True on success, False on failure.
        """
        # Use SSML for rate control
        ssml = f"""
        <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis'
               xml:lang='en-PH'>
          <voice name='{voice}'>
            <prosody rate='{rate}'>
              {text}
            </prosody>
          </voice>
        </speak>
        """

        audio_config = speechsdk.AudioConfig(filename=output_path)
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self.speech_config,
            audio_config=audio_config,
        )

        result = synthesizer.speak_ssml_async(ssml).get()
        return result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted

    def transcribe_streaming(self, audio_stream) -> str:
        """
        Real-time streaming transcription for live tablet sessions.
        Returns the full transcription when the speaker pauses.
        """
        stream_config = speechsdk.audio.AudioStreamFormat(
            samples_per_second=16000,
            bits_per_sample=16,
            channels=1,
        )
        push_stream = speechsdk.audio.PushAudioInputStream(stream_config)
        audio_config = speechsdk.AudioConfig(stream=push_stream)

        recognizer = speechsdk.SpeechRecognizer(
            speech_config=self.speech_config,
            audio_config=audio_config,
        )

        transcription = []

        def on_recognized(evt):
            transcription.append(evt.result.text)

        recognizer.recognized.connect(on_recognized)
        recognizer.start_continuous_recognition()

        # Write audio chunks
        for chunk in audio_stream:
            push_stream.write(chunk)

        push_stream.close()
        recognizer.stop_continuous_recognition()

        return " ".join(transcription)
