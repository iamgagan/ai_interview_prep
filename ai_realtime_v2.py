import os
import threading
import pyaudio
import queue
import base64
import json
import time
import logging
from websocket import create_connection, WebSocketConnectionClosedException
import PyPDF2
import docx
import speech_recognition as sr
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer

nltk.download('vader_lexicon', quiet=True)

class FinanceInterviewerAI:
    def __init__(self, api_key, job_params):
        self.API_KEY = api_key
        self.job_params = job_params
        self.WS_URL = 'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01'
        
        # Audio configuration
        self.CHUNK_SIZE = 1024
        self.RATE = 24000
        self.FORMAT = pyaudio.paInt16
        self.REENGAGE_DELAY_MS = 500

        # State management
        self.audio_buffer = bytearray()
        self.mic_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.mic_on_at = 0
        self.mic_active = None

        # Interview tracking
        self.current_question = 0
        self.last_question_type = None
        self.responses = []
        
        # Analysis tools
        self.recognizer = sr.Recognizer()
        self.sia = SentimentIntensityAnalyzer()
        
        # Setup logging
        logging.basicConfig(level=logging.INFO, 
                          format='%(asctime)s [%(levelname)s] %(message)s')
        
        # Initialize prompts
        self.initial_message = self._generate_initial_message()
        self.new_question_prompt = self._generate_new_question_prompt()
        self.related_question_prompt = self._generate_related_question_prompt()
        self.feedback_prompt = self._generate_feedback_prompt()

    def _generate_initial_message(self):
        """Generate the initial interview message based on the template."""
        return f"""Interview me for a {self.job_params['job_title']} position at {self.job_params['company_name']} within the {self.job_params['industry']} industry. Focus on the {self.job_params['industry_focus']} industry coverage group {self.job_params['vertical']}. The product speciality is {self.job_params['product_group']}. The questions should consist of a balanced mix of technical and problem-solving questions focused exclusively on {self.job_params['category']}. Avoid explicitly mentioning the category during the interview.

On a scale from 1 to 5, the interview difficulty should be {self.job_params['difficulty']}.

We will do a question-by-question mock interview. You will strictly follow this format:
1. Ask one question at a time, prefixed by "QUESTION:"
2. After I answer, you provide feedback, prefixed by "FEEDBACK:"
3. Then I will choose a new or related question.

Let's begin. Please ask me the first question now."""

    def _generate_new_question_prompt(self):
        """Generate the prompt for requesting a new question."""
        return "Ask me a completely new question related to the interview. Provide feedback on the answer received."

    def _generate_related_question_prompt(self):
        """Generate the prompt for requesting a related question."""
        return "Ask me a new question related to the last one. Provide feedback on the answer received."

    def _generate_feedback_prompt(self):
        """Generate the prompt for requesting comprehensive feedback."""
        return """Please provide a comprehensive and honest evaluation of my performance during the interview. Highlight my strengths and areas where I can improve, focusing on aspects such as:
- Communication skills
- Technical knowledge
- Problem-solving abilities
- Overall presentation"""

    def mic_callback(self, in_data, frame_count, time_info, status):
        """Handle microphone input and manage voice activity detection."""
        if time.time() > self.mic_on_at:
            if self.mic_active != True:
                logging.info('🎙️🟢 Mic active')
                self.mic_active = True
            self.mic_queue.put(in_data)
        else:
            if self.mic_active != False:
                logging.info('🎙️🔴 Mic suppressed')
                self.mic_active = False
        return (None, pyaudio.paContinue)

    def spkr_callback(self, in_data, frame_count, time_info, status):
        """Handle speaker output and buffer management."""
        bytes_needed = frame_count * 2
        current_buffer_size = len(self.audio_buffer)

        if current_buffer_size >= bytes_needed:
            audio_chunk = bytes(self.audio_buffer[:bytes_needed])
            self.audio_buffer = self.audio_buffer[bytes_needed:]
            self.mic_on_at = time.time() + self.REENGAGE_DELAY_MS / 1000
        else:
            audio_chunk = bytes(self.audio_buffer) + b'\x00' * (bytes_needed - current_buffer_size)
            self.audio_buffer.clear()

        return (audio_chunk, pyaudio.paContinue)

    def send_mic_audio(self, ws):
        """Send microphone audio to WebSocket."""
        try:
            while not self.stop_event.is_set():
                if not self.mic_queue.empty():
                    mic_chunk = self.mic_queue.get()
                    logging.info(f'🎤 Sending {len(mic_chunk)} bytes of audio data.')
                    encoded_chunk = base64.b64encode(mic_chunk).decode('utf-8')
                    message = json.dumps({
                        'type': 'input_audio_buffer.append', 
                        'audio': encoded_chunk
                    })
                    ws.send(message)
                    # Process the audio for transcription and analysis
                    self.process_audio(mic_chunk)
                time.sleep(0.1)  # Small delay to prevent busy waiting
        except WebSocketConnectionClosedException:
            logging.error('WebSocket connection closed.')
        except Exception as e:
            logging.error(f'Error in send_mic_audio: {e}')
        finally:
            logging.info('Exiting send_mic_audio thread.')

    def receive_audio(self, ws):
        """Receive and process audio from WebSocket."""
        try:
            while not self.stop_event.is_set():
                message = ws.recv()
                if not message:
                    logging.info('🔵 Received empty message.')
                    continue

                message = json.loads(message)
                event_type = message['type']
                logging.info(f'⚡️ Received WebSocket event: {event_type}')

                if event_type == 'response.audio.delta':
                    audio_content = base64.b64decode(message['delta'])
                    self.audio_buffer.extend(audio_content)
                    logging.info(f'🔵 Received {len(audio_content)} bytes, buffer: {len(self.audio_buffer)}')
                elif event_type == 'response.audio.done':
                    logging.info('🔵 AI finished speaking.')
                elif event_type == 'response.text':
                    logging.info(f'📝 Received text: {message.get("text", "")}')

        except Exception as e:
            logging.error(f'Error in receive_audio: {e}')
        finally:
            logging.info('Exiting receive_audio thread.')

    def process_audio(self, audio_chunk):
        """Process received audio chunks for transcription and analysis."""
        try:
            # Convert audio chunk to wav format for speech recognition
            with open("temp_audio.wav", "wb") as f:
                f.write(audio_chunk)

            with sr.AudioFile("temp_audio.wav") as source:
                audio = self.recognizer.record(source)
                try:
                    text = self.recognizer.recognize_google(audio)
                    logging.info(f'Transcribed text: {text}')
                    # Store response for analysis
                    self.responses.append(text)
                except sr.UnknownValueError:
                    logging.debug('Speech not recognized')
                except sr.RequestError as e:
                    logging.error(f'Error with speech recognition service: {e}')

        except Exception as e:
            logging.error(f'Error processing audio: {e}')
        finally:
            # Cleanup temporary file
            if os.path.exists("temp_audio.wav"):
                os.remove("temp_audio.wav")

    def start_interview(self):
        """Start the interview session with the initial message."""
        try:
            # Initialize WebSocket connection
            ws = create_connection(
                self.WS_URL,
                header=[
                    f'Authorization: Bearer {self.API_KEY}',
                    'OpenAI-Beta: realtime=v1'
                ]
            )
            logging.info('Connected to WebSocket')
            
            # Send initial message
            ws.send(json.dumps({
                'type': 'response.create',
                'response': {
                    'modalities': ['audio', 'text'],
                    'instructions': self.initial_message
                }
            }))
            logging.info('Sent initial message')
            
            # Start audio processing
            self._setup_audio_streams(ws)
            
        except Exception as e:
            logging.error(f"Error starting interview: {e}")
            raise

    def _setup_audio_streams(self, ws):
        """Set up audio streams for the interview."""
        p = pyaudio.PyAudio()

        try:
            # Setup audio streams
            mic_stream = p.open(
                format=self.FORMAT,
                channels=1,
                rate=self.RATE,
                input=True,
                stream_callback=self.mic_callback,
                frames_per_buffer=self.CHUNK_SIZE
            )

            spkr_stream = p.open(
                format=self.FORMAT,
                channels=1,
                rate=self.RATE,
                output=True,
                stream_callback=self.spkr_callback,
                frames_per_buffer=self.CHUNK_SIZE
            )

            mic_stream.start_stream()
            spkr_stream.start_stream()

            # Start processing threads
            receive_thread = threading.Thread(target=self.receive_audio, args=(ws,))
            mic_thread = threading.Thread(target=self.send_mic_audio, args=(ws,))
            
            receive_thread.start()
            mic_thread.start()

            # Main interview loop
            try:
                while not self.stop_event.is_set():
                    time.sleep(0.1)
            except KeyboardInterrupt:
                logging.info("Interview interrupted by user")
                self.stop_event.set()

            # Wait for threads to complete
            receive_thread.join()
            mic_thread.join()

        finally:
            # Cleanup
            mic_stream.stop_stream()
            mic_stream.close()
            spkr_stream.stop_stream()
            spkr_stream.close()
            p.terminate()
            ws.close()
            logging.info('Interview session completed')

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file."""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ''
            for page in reader.pages:
                text += page.extract_text() + '\n'
        return text
    except Exception as e:
        logging.error(f"Error reading PDF file: {e}")
        return None

def extract_text_from_docx(docx_path):
    """Extract text from a Word document."""
    try:
        doc = docx.Document(docx_path)
        text = '\n'.join([paragraph.text for paragraph in doc.paragraphs])
        return text
    except Exception as e:
        logging.error(f"Error reading Word file: {e}")
        return None

def main():
    try:
        # Get interview parameters
        job_params = {
            'job_title': input("Enter the job title: "),
            'company_name': input("Enter the company name: "),
            'industry': input("Enter the industry: "),
            'industry_focus': input("Enter the industry focus: "),
            'vertical': input("Enter the vertical: "),
            'product_group': input("Enter the product group: "),
            'difficulty': int(input("Enter interview difficulty (1-5): ")),
            'category': input("Enter interview category (Technical/Behavioral): "),
            'duration': input("Enter interview duration (minutes): ")
        }

        # Optional resume input
        resume_path = input("Enter path to resume file (optional, press Enter to skip): ").strip()
        if resume_path and os.path.exists(resume_path):
            if resume_path.lower().endswith('.pdf'):
                job_params['resume_text'] = extract_text_from_pdf(resume_path)
            elif resume_path.lower().endswith('.docx'):
                job_params['resume_text'] = extract_text_from_docx(resume_path)
            else:
                print("Unsupported file format. Only PDF and DOCX are supported.")

        # Get API key
        api_key = input("Enter your OpenAI API key: ").strip()
        if not api_key:
            raise ValueError("API key is required")

        # Initialize and start interview
        interviewer = FinanceInterviewerAI(api_key, job_params)
        interviewer.start_interview()

    except KeyboardInterrupt:
        print("\nInterview terminated by user.")
    except Exception as e:
        print(f"An error occurred: {e}")
        logging.error(f"Error in main: {e}")

if __name__ == '__main__':
    main()
