import os
import threading
import pyaudio
import queue
import base64
import json
import time
import random
import logging
from websocket import create_connection, WebSocketConnectionClosedException

# Import libraries for reading PDF and Word documents
import PyPDF2
import docx

# Import speech recognition and NLP libraries
import speech_recognition as sr
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer

# Download NLTK data if not already present
nltk.download('vader_lexicon', quiet=True)

class FinanceInterviewerAI:
    def __init__(self, api_key, role_type=None, resume_text=None, difficulty='Intermediate', topics=None):
        self.API_KEY = api_key
        self.role_type = role_type
        self.resume_text = resume_text
        self.difficulty = difficulty
        self.topics = topics if topics else []
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

        # For feedback and scoring
        self.recognizer = sr.Recognizer()
        self.sia = SentimentIntensityAnalyzer()
        self.user_responses = []
        self.scores = []
        self.feedback = []

        # Setup logging
        logging.basicConfig(level=logging.INFO, 
                          format='%(asctime)s [%(levelname)s] %(message)s')
        
        # Interview context setup
        self.interview_context = self._generate_interview_context()

    def _generate_interview_context(self):
        """Generate the interview context with role-specific focus areas."""
        role_specific_focus = {
            "Investment Banking": """**Technical Focus Areas**:
    - Valuation methodologies (DCF, Comparable Companies, Precedent Transactions)
    - M&A process knowledge
    - Financial modeling expertise
    - Deal experience
    - Industry knowledge
    - Client interaction skills""",
            
            "Private Equity": """**Technical Focus Areas**:
    - Investment thesis development
    - Portfolio company management
    - Operational improvement strategies
    - Deal sourcing and execution
    - Exit strategies
    - Value creation plans""",
            
            "Venture Capital": """**Technical Focus Areas**:
    - Startup evaluation metrics
    - Market sizing and growth analysis
    - Technology trends
    - Founder assessment
    - Scale-up strategies
    - Early-stage valuation methods""",
            
            "Growth Equity": """**Technical Focus Areas**:
    - Scale-up execution
    - Unit economics
    - Market expansion strategies
    - Competition analysis
    - Growth metrics
    - Revenue optimization""",
            
            "Equity Research": """**Technical Focus Areas**:
    - Industry analysis frameworks
    - Financial modeling depth
    - Stock recommendation process
    - Thesis development and testing
    - Information synthesis
    - Written and verbal communication""",
            
            "Debt Capital Markets": """**Technical Focus Areas**:
    - Credit analysis
    - Fixed income products
    - Capital structure optimization
    - Rating agency considerations
    - Market conditions impact
    - Covenant analysis""",
            
            "Equity Capital Markets": """**Technical Focus Areas**:
    - IPO process knowledge
    - Follow-on offerings
    - Market timing
    - Investor relations
    - Book building process
    - Pricing strategies""",
        }
        
        base_context = f"""You are an experienced Wall Street interviewer specializing in {self.role_type}. 
    Your role is to conduct a structured interview to assess the candidate's technical knowledge and fit for the {self.role_type} role.

    **Interview Structure**:
    1. **Resume-Based Questions** (Ask exactly 2 questions):
        - Focus on the candidate's past experiences, achievements, and skills as mentioned in their resume.
    2. **Technical Questions**:
        - Dive into technical topics specific to {self.role_type}.
        - Focus on assessing the candidate's expertise in key technical areas.
    3. **Behavioral Questions**:
        - Conclude with questions that assess the candidate's soft skills, problem-solving abilities, and cultural fit.

    **Guidelines**:
    - **Do Not** ask general questions about the candidate's interests unless directly related to the role.
    - **Keep the Conversation Professional and Focused** on assessing qualifications.
    - **Use the Candidate's Resume** to inform your resume-based questions.
    - **Follow the Interview Structure** strictly without deviation.
    - **Ask Clear and Concise Questions**.
    - **Avoid Unrelated Topics**.

    {role_specific_focus.get(self.role_type, "")}

    **Candidate's Resume**:
    {self.resume_text if self.resume_text else "No resume provided."}

    **Important Notes**:
    - Do not deviate from the interview structure.
    - Keep questions relevant to the {self.role_type} role.
    - Maintain a professional tone throughout the interview.
    """

        return base_context

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
                    # Process the user's response for feedback
                    self.process_user_response(mic_chunk)
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
                    break

                message = json.loads(message)
                event_type = message['type']
                logging.info(f'⚡️ Received WebSocket event: {event_type}')

                if event_type == 'response.audio.delta':
                    audio_content = base64.b64decode(message['delta'])
                    self.audio_buffer.extend(audio_content)
                    logging.info(f'🔵 Received {len(audio_content)} bytes, buffer: {len(self.audio_buffer)}')
                elif event_type == 'response.audio.done':
                    logging.info('🔵 AI finished speaking.')

        except Exception as e:
            logging.error(f'Error in receive_audio: {e}')
        finally:
            logging.info('Exiting receive_audio thread.')

    def process_user_response(self, audio_chunk):
        """Transcribe and analyze the user's response."""
        # Save audio chunk to a temporary WAV file
        with open("temp_response.wav", "wb") as f:
            f.write(audio_chunk)
        # Transcribe using SpeechRecognition
        try:
            with sr.AudioFile("temp_response.wav") as source:
                audio = self.recognizer.record(source)
            response_text = self.recognizer.recognize_google(audio)
            self.user_responses.append(response_text)
            logging.info(f'User response transcribed: {response_text}')
            # Analyze the response and provide feedback
            score, feedback = self.analyze_response(response_text)
            self.scores.append(score)
            self.feedback.append(feedback)
            logging.info(f'Feedback: {feedback} | Score: {score}')
            # Optionally, speak out the feedback (implementation depends on your design)
        except Exception as e:
            logging.error(f'Error transcribing audio: {e}')

    def analyze_response(self, response_text):
        """Analyze the transcribed response and provide feedback."""
        # Placeholder analysis - you can implement more complex NLP here
        # For demonstration, we'll use sentiment analysis as a proxy
        sentiment = self.sia.polarity_scores(response_text)
        score = sentiment['compound']
        if score >= 0.05:
            feedback = "Positive response."
        elif score <= -0.05:
            feedback = "Negative response."
        else:
            feedback = "Neutral response."
        return score, feedback

    def provide_post_interview_feedback(self):
        """Provide a summary of the interview and recommendations."""
        average_score = sum(self.scores) / len(self.scores) if self.scores else 0
        print("\n--- Interview Summary ---")
        print(f"Average Score: {average_score:.2f}")
        # Provide recommendations based on average score
        if average_score > 0.5:
            print("Great job! You performed well in this interview.")
        elif average_score > 0:
            print("Good effort! Consider improving in certain areas.")
        else:
            print("You might want to focus on improving your technical knowledge and communication skills.")
        # Recommend resources
        print("\n--- Recommended Resources ---")
        print("- Financial Modeling courses on Coursera or Udemy.")
        print("- Books on investment banking and finance.")
        print("- Practice technical questions on financial forums.")

    def start_interview(self):
        """Start the interview session."""
        p = pyaudio.PyAudio()

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

        try:
            # Start audio streams
            mic_stream.start_stream()
            spkr_stream.start_stream()

            # Connect to WebSocket
            ws = create_connection(
                self.WS_URL,
                header=[
                    f'Authorization: Bearer {self.API_KEY}',
                    'OpenAI-Beta: realtime=v1'
                ]
            )
            logging.info('Connected to OpenAI WebSocket.')

            # Initialize interview session
            ws.send(json.dumps({
                'type': 'response.create',
                'response': {
                    'modalities': ['audio', 'text'],
                    'instructions': self.interview_context
                }
            }))

            # Start processing threads
            receive_thread = threading.Thread(target=self.receive_audio, args=(ws,))
            mic_thread = threading.Thread(target=self.send_mic_audio, args=(ws,))
            
            receive_thread.start()
            mic_thread.start()

            # Main loop
            try:
                while mic_stream.is_active() and spkr_stream.is_active():
                    time.sleep(0.1)
            except KeyboardInterrupt:
                logging.info('Interview session ending...')
                self.stop_event.set()

            # Cleanup
            ws.close()
            receive_thread.join()
            mic_thread.join()

        finally:
            mic_stream.stop_stream()
            mic_stream.close()
            spkr_stream.stop_stream()
            spkr_stream.close()
            p.terminate()
            logging.info('Interview session completed.')
            # Provide post-interview feedback
            self.provide_post_interview_feedback()

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file."""
    text = ""
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text
    except Exception as e:
        logging.error(f"Error reading PDF file: {e}")
        return None
    return text

def extract_text_from_docx(docx_path):
    """Extract text from a Word (.docx) file."""
    text = ""
    try:
        doc = docx.Document(docx_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    except Exception as e:
        logging.error(f"Error reading Word file: {e}")
        return None
    return text

def main():
    # Available roles
    FINANCE_ROLES = [
        "Investment Banking",
        "Private Equity",
        "Venture Capital",
        "Growth Equity",
        "Equity Research",
        "Debt Capital Markets",
        "Equity Capital Markets"
    ]

    # Prompt user for API key securely
    API_KEY = input("Enter your OpenAI API key: ").strip()
    if not API_KEY:
        print("API key is required to proceed.")
        return

    # Role selection with validation
    print("\nAvailable roles:")
    for idx, role in enumerate(FINANCE_ROLES, 1):
        print(f"{idx}. {role}")
    while True:
        try:
            role_choice = int(input("Select a role by entering the corresponding number: "))
            if 1 <= role_choice <= len(FINANCE_ROLES):
                selected_role = FINANCE_ROLES[role_choice - 1]
                break
            else:
                print(f"Please enter a number between 1 and {len(FINANCE_ROLES)}.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    # Difficulty level selection
    difficulty_levels = ["Beginner", "Intermediate", "Advanced"]
    print("\nDifficulty Levels:")
    for idx, level in enumerate(difficulty_levels, 1):
        print(f"{idx}. {level}")
    while True:
        try:
            difficulty_choice = int(input("Select a difficulty level: "))
            if 1 <= difficulty_choice <= len(difficulty_levels):
                selected_difficulty = difficulty_levels[difficulty_choice - 1]
                break
            else:
                print(f"Please enter a number between 1 and {len(difficulty_levels)}.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    # Topic selection
    print("\nAvailable Topics:")
    default_topics = [
        "Technical financial knowledge",
        "Market understanding and current events",
        "Problem-solving abilities",
        "Past experience and achievements",
        "Leadership and teamwork scenarios",
        "Deal/transaction experience",
        "Investment thesis and analysis approach",
        "Risk assessment and management",
        "Industry knowledge and trends"
    ]
    for idx, topic in enumerate(default_topics, 1):
        print(f"{idx}. {topic}")
    print("Enter the numbers of the topics you want to focus on, separated by commas (e.g., 1,3,5).")
    print("Leave empty to select all topics.")
    topic_input = input("Your choice: ").strip()
    if topic_input:
        try:
            topic_indices = [int(i.strip()) - 1 for i in topic_input.split(",") if i.strip()]
            selected_topics = [default_topics[i] for i in topic_indices if 0 <= i < len(default_topics)]
        except ValueError:
            print("Invalid input. All topics will be selected.")
            selected_topics = default_topics
    else:
        selected_topics = default_topics

    # Resume file path input with validation
    while True:
        resume_file_path = input("\nEnter the path to your resume file (PDF or DOCX): ").strip()
        if not os.path.isfile(resume_file_path):
            print("File not found. Please enter a valid file path.")
            continue
        if not resume_file_path.lower().endswith(('.pdf', '.docx')):
            print("Unsupported file format. Please provide a PDF or DOCX file.")
            continue
        break

    # Determine file type and extract text
    if resume_file_path.lower().endswith('.pdf'):
        resume_text = extract_text_from_pdf(resume_file_path)
        if resume_text is None:
            print("Failed to extract text from the PDF file.")
            return
    elif resume_file_path.lower().endswith('.docx'):
        resume_text = extract_text_from_docx(resume_file_path)
        if resume_text is None:
            print("Failed to extract text from the Word file.")
            return
    else:
        print("Unsupported file format. Please provide a PDF or DOCX file.")
        return

    # Confirm starting the interview
    print(f"\nStarting an interview for the role: {selected_role}")
    print(f"Difficulty Level: {selected_difficulty}")
    print(f"Selected Topics: {', '.join(selected_topics)}")
    print("Press Enter to begin...")
    input()

    # Initialize and start the interview
    interviewer = FinanceInterviewerAI(
        API_KEY, 
        role_type=selected_role, 
        resume_text=resume_text,
        difficulty=selected_difficulty,
        topics=selected_topics
    )
    interviewer.start_interview()

if __name__ == '__main__':
    main()
