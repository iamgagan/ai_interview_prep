import os
import json
import re
import random
from PyPDF2 import PdfReader
from openai import OpenAI
import pygame
import speech_recognition as sr
from gtts import gTTS
import tempfile
import speech_recognition as sr
import time
import threading
import queue
import logging
import threading
import pyaudio
import wave

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


# Ensure you set your OpenAI API key as an environment variable for security
OPENAI_API_KEY = api_key
if not OPENAI_API_KEY:
    raise ValueError("No OpenAI API key found. Please set the OPENAI_API_KEY environment variable.")


class AIInterviewPrep:
    def __init__(self):
        self.job_position = ""
        self.industry = ""
        self.industry_coverage = ""
        self.vertical = ""
        self.job_description = ""
        self.candidate_cv = ""
        self.interview_history = []
        self.scores = []
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.speech_file_path = "speech.mp3"
        self.use_voice_input = True
        self.conversation_context = ""
        self.question_counter = 0
        self.microphone = sr.Microphone()
        self.recognizer = sr.Recognizer()

        self.industries = [
            "Investment Banking", "Private Equity", "Real Estate Finance", "Venture Capital",
            "Growth Equity", "Asset Management", "Sales & Trading", "Hedge Fund",
            "Equity Research", "Debt Capital Markets", "Equity Capital Markets", "Consulting",
            "Accounting", "Corporate Finance", "Wealth Management", "Commercial Banking",
            "Insurance", "Structured Finance"
        ]
        self.blue_industries = [
            "Investment Banking", "Private Equity", "Venture Capital", "Growth Equity",
            "Equity Research", "Debt Capital Markets", "Equity Capital Markets"
        ]
        self.industry_coverage_options = [
            "None", "Healthcare", "Real Estate, Gaming, & Lodging (REGAL)", 
            "Technology, Media & Telecom (TMT)", "Financial Sponsors Group (FSG)",
            "Financial Institutions Group (FIG)", "Technology", "Industrials",
            "Public Finance", "Restructuring (Rx)", "Oil & Gas", "Consumer Retail",
            "Infrastructure", "Renewable Energy", "Power & Utilities", 
            "Business Services", "Food & Beverage"
        ]
        self.orange_options = [
            "Healthcare", "Real Estate, Gaming, & Lodging (REGAL)", 
            "Financial Sponsors Group (FSG)", "Technology", "Industrials",
            "Oil & Gas", "Consumer Retail", "Food & Beverage"
        ]
        self.verticals = ["Depositories", "Insurance", "Specialty Finance", "Asset Management", "FinTech"]

    def text_to_speech(self, text):
        try:
            response = self.client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=text
            )
            with open(self.speech_file_path, "wb") as f:
                f.write(response.content)

            pygame.mixer.init()
            pygame.mixer.music.load(self.speech_file_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        except Exception as e:
            print(f"Text-to-speech failed. Error: {e}")
            print("Continuing without voice output.")



    def speech_to_text(self):
        logging.debug("Entering speech_to_text method")
        
        # Set up PyAudio
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 44100
        
        p = pyaudio.PyAudio()
        
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)

        print("Recording... Press Enter to stop.")
        
        frames = []
        recording = True

        def input_thread():
            nonlocal recording
            input()
            recording = False

        thread = threading.Thread(target=input_thread)
        thread.start()

        while recording:
            data = stream.read(CHUNK)
            frames.append(data)

        print("Finished recording")

        stream.stop_stream()
        stream.close()
        p.terminate()

        # Save the recorded data as a WAV file
        wf = wave.open("temp.wav", 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()

        # Perform speech recognition on the recorded file
        recognizer = sr.Recognizer()
        with sr.AudioFile("temp.wav") as source:
            audio = recognizer.record(source)

        try:
            text = recognizer.recognize_google(audio)
            logging.debug(f"Speech recognized: {text}")
            return text
        except sr.UnknownValueError:
            print("Google Speech Recognition could not understand audio")
            return None
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {e}")
            return None

    def extract_text_from_pdf(self, file_path):
        try:
            with open(file_path, 'rb') as file:
                pdf = PdfReader(file)
                text = ""
                for page in pdf.pages:
                    text += page.extract_text()
            return text
        except Exception as e:
            print(f"Error reading PDF: {e}")
            return ""

    def setup_interview(self):
        print("Welcome to the Enhanced AI Interview Prep App!")
        self.text_to_speech("Welcome to the Enhanced AI Interview Prep App!")

        self.job_position = input("Enter the job position: ")
        
        print("Select the industry:")
        for i, industry in enumerate(self.industries, 1):
            print(f"{i}. {industry}")
        
        while True:
            try:
                industry_choice = int(input("Enter the number of your choice: "))
                if 1 <= industry_choice <= len(self.industries):
                    self.industry = self.industries[industry_choice - 1]
                    break
                else:
                    print("Invalid choice. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
        
        if self.industry in self.blue_industries:
            print("Select Industry Coverage:")
            for i, coverage in enumerate(self.industry_coverage_options, 1):
                print(f"{i}. {coverage}")
            
            while True:
                try:
                    coverage_choice = int(input("Enter the number of your choice: "))
                    if 1 <= coverage_choice <= len(self.industry_coverage_options):
                        self.industry_coverage = self.industry_coverage_options[coverage_choice - 1]
                        break
                    else:
                        print("Invalid choice. Please try again.")
                except ValueError:
                    print("Please enter a valid number.")
            
            if self.industry_coverage in self.orange_options:
                print(f"Select Vertical for {self.industry_coverage}:")
                for i, vertical in enumerate(self.verticals, 1):
                    print(f"{i}. {vertical}")
                
                while True:
                    try:
                        vertical_choice = int(input("Enter the number of your choice: "))
                        if 1 <= vertical_choice <= len(self.verticals):
                            self.vertical = self.verticals[vertical_choice - 1]
                            break
                        else:
                            print("Invalid choice. Please try again.")
                    except ValueError:
                        print("Please enter a valid number.")

        self.job_description = self.get_multiline_input("Enter the job description (press Enter twice when finished):")

        while True:
            cv_path = input("Enter the full path to your CV (PDF file): ")
            self.candidate_cv = self.extract_text_from_pdf(cv_path)
            if self.candidate_cv:
                break
            else:
                print("Failed to read the CV. Please ensure the file path is correct and the file is a valid PDF.")

        self.use_voice_input = self.get_yes_no_input("Would you like to use voice input for your responses?")

    def get_multiline_input(self, prompt):
        print(prompt)
        lines = []
        while True:
            line = input()
            if line:
                lines.append(line)
            else:
                break
        return '\n'.join(lines)

    def get_yes_no_input(self, question):
        while True:
            response = input(f"{question} (yes/no): ").lower()
            if response in ['yes', 'y']:
                return True
            elif response in ['no', 'n']:
                return False
            else:
                print("Please answer with 'yes' or 'no'.")

    def generate_question(self):
        self.question_counter += 1
        
        if self.question_counter == 1:
            return "Tell me about your background and why you're interested in this position."

        prompt = f"""
        You are an experienced interviewer conducting an interview for the position of {self.job_position} 
        in the {self.industry} industry.
        
        Additional context:
        Industry Coverage: {self.industry_coverage if self.industry_coverage else "Not specified"}
        Vertical: {self.vertical if self.vertical else "Not specified"}
        
        Job Description: {self.job_description}
        Candidate's CV: {self.candidate_cv}
        Previous conversation context: {self.conversation_context}

        This is question number {self.question_counter} in the interview.

        Generate the next interview question based on this information and the conversation so far. 

        The question should:
        1. Be natural and conversational, as if coming from a human interviewer
        2. Follow up on information provided in previous responses and the candidate's CV
        3. Be highly relevant and specific to the chosen industry: {self.industry}
        4. If applicable, focus on the selected Industry Coverage: {self.industry_coverage}
        5. If a Vertical was selected, include aspects specific to: {self.vertical}
        6. Avoid repeating questions that have already been asked
        7. Gradually increase in difficulty and specificity as the interview progresses

        Special instructions:
        - For questions 2-4, focus on personal or behavioral questions related to the industry and role
        - After question 4, ask more technical and role-specific questions directly related to {self.industry}
        - If Industry Coverage was selected, ensure questions reflect knowledge specific to {self.industry_coverage}
        - If a Vertical was chosen, include questions that test expertise in {self.vertical}
        - Always maintain a friendly and engaging tone throughout the interview

        Ensure the question flows naturally from the previous conversation and delves deeper into the candidate's experiences and qualifications,
        while being highly relevant to the specific industry, coverage, and vertical selected.
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an AI-powered interview assistant generating natural, context-aware, and highly specific interview questions."},
                    {"role": "user", "content": prompt}
                ]
            )

            question = response.choices[0].message.content.strip()
            self.interview_history.append({"role": "interviewer", "content": question})
            return question
        except Exception as e:
            logging.exception(f"Error generating question: {e}")
            return "Could you tell me more about your experience in this field?"

    def evaluate_response(self, response):
        if response.lower() == 'quit':
            return None, None

        last_question = self.interview_history[-1]['content'] if self.interview_history else "Tell me about your background and why you're interested in this position."

        prompt = f"""
        Evaluate the following candidate response to the last interview question:
        Job Position: {self.job_position}
        Industry: {self.industry}
        Industry Coverage: {self.industry_coverage if self.industry_coverage else "Not specified"}
        Vertical: {self.vertical if self.vertical else "Not specified"}
        Job Description: {self.job_description}
        Last Question: {last_question}
        Candidate Response: {response}
        Candidate's CV: {self.candidate_cv}
        Interview History: {self.interview_history}

        Provide three separate outputs:
        1. A natural follow-up comment based on the candidate's response. 
        This should sound like a human interviewer's reaction and may include:
        - Acknowledgment of the candidate's response
        - A brief comment or insight related to their answer
        - A smooth transition to the next topic or question
        2. A hidden evaluation for internal use.
        3. A boolean indicating if the response was substantive and relevant (True) or not (False).

        Format your response as follows:
        <interviewer_response>
        [Natural follow-up comment]
        </interviewer_response>

        <hidden_evaluation>
        Score: [score from 0 to 10]
        Strengths: [brief notes on strengths]
        Improvement Areas: [brief notes on areas for improvement]
        </hidden_evaluation>

        <response_quality>
        [True/False]
        </response_quality>
        """

        try:
            evaluation = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an AI-powered interview evaluator providing natural feedback and hidden evaluations."},
                    {"role": "user", "content": prompt}
                ]
            )

            eval_result = evaluation.choices[0].message.content.strip()

            interviewer_response_match = re.search(r'<interviewer_response>(.*?)</interviewer_response>', eval_result, re.DOTALL)
            interviewer_response = interviewer_response_match.group(1).strip() if interviewer_response_match else "Thank you for your response."

            hidden_eval_match = re.search(r'<hidden_evaluation>(.*?)</hidden_evaluation>', eval_result, re.DOTALL)
            hidden_evaluation = hidden_eval_match.group(1).strip() if hidden_eval_match else "No hidden evaluation available."

            response_quality_match = re.search(r'<response_quality>(.*?)</response_quality>', eval_result, re.DOTALL)
            response_quality = response_quality_match.group(1).strip().lower() == 'true' if response_quality_match else False

            score_match = re.search(r'Score:\s*(\d+(?:\.\d+)?)', hidden_evaluation)
            if score_match:
                score = float(score_match.group(1))
                self.scores.append(score)
            else:
                logging.warning("Could not extract score from evaluation. Using default score of 5.")
                self.scores.append(5)

            self.interview_history.append({"role": "candidate", "content": response})
            self.interview_history.append({"role": "interviewer", "content": interviewer_response})
            self.interview_history.append({"role": "evaluator", "content": hidden_evaluation})
            
            self.conversation_context += f"\nInterviewer: {last_question}\nCandidate: {response}\nInterviewer: {interviewer_response}\n"

            return interviewer_response, hidden_evaluation, response_quality
        except Exception as e:
            logging.exception(f"Error in evaluating response: {e}")
            return "Thank you for your response. Let's move on to the next question.", "Error in evaluation", False

    def run_interview(self):
        logging.debug("Starting run_interview method")
        try:
            self.setup_interview()
            
            print("\nGreat! Let's start the interview. Type 'quit' at any time to end the session and evaluate.\n")
            self.text_to_speech("Great! Let's start the interview. Type 'quit' at any time to end the session and evaluate.")

            question_count = 0
            while True:
                question = self.generate_question()
                print(f"\nInterviewer: {question}")
                self.text_to_speech(question)

                while True:
                    print("\nHow would you like to provide your answer?")
                    print("1. Text input")
                    print("2. Voice input")
                    choice = input("Enter your choice (1 or 2): ")

                    if choice == '1':
                        print("Type your answer. Type 'done' on a new line when finished, or 'quit' to end the interview.")
                        response_lines = []
                        while True:
                            line = input()
                            if line.lower() == 'done':
                                break
                            if line.lower() == 'quit':
                                return self.evaluate_interview()
                            response_lines.append(line)
                        response = '\n'.join(response_lines)
                        break
                    elif choice == '2':
                        print("Please speak your answer. Press Enter to start speaking, and press Enter again when you're finished.")
                        input("Press Enter to start speaking...")
                        try:
                            response = self.speech_to_text()
                            if response:
                                print(f"\nRecognized speech:\n{response}")
                                confirm = input("Is this correct? (yes/no): ").lower()
                                if confirm == 'yes':
                                    break
                                elif confirm == 'quit':
                                    return self.evaluate_interview()
                                else:
                                    print("Let's try again.")
                            else:
                                print("No speech detected. Let's try again.")
                        except Exception as e:
                            logging.exception(f"Exception in speech recognition: {e}")
                            print(f"An error occurred: {e}. Let's try again.")
                    else:
                        print("Invalid choice. Please enter 1 or 2.")

                print("\nYour answer:")
                print(response)

                logging.debug("Evaluating response")
                try:
                    interviewer_response, hidden_evaluation, response_quality = self.evaluate_response(response)
                except Exception as e:
                    logging.exception(f"Error in evaluating response: {e}")
                    print("An error occurred while evaluating your response. Let's try this question again.")
                    continue

                if not response_quality:
                    print("I'm sorry, but your response doesn't seem to address the question fully. Could you please provide a more detailed and relevant answer?")
                    continue

                print(f"\nInterviewer: {interviewer_response}")
                self.text_to_speech(interviewer_response)

                if os.environ.get('DEBUG_MODE') == 'TRUE':
                    print(f"\nHidden Evaluation:\n{hidden_evaluation}\n")

                question_count += 1
                
                if question_count >= 10:
                    print("\nWe've reached the end of the planned questions. Would you like to continue or end the interview?")
                    choice = input("Enter 'continue' to keep going or 'quit' to end and evaluate: ").lower()
                    if choice == 'quit':
                        return self.evaluate_interview()

        except Exception as e:
            logging.exception(f"An unexpected error occurred during the interview: {e}")
            print(f"An unexpected error occurred: {e}")
            print("We apologize for the inconvenience. The application will now exit.")
            self.text_to_speech("An unexpected error occurred. The application will now exit.")

    def evaluate_interview(self):
        logging.debug("Evaluating entire interview")
        if self.scores:
            average_score = sum(self.scores) / len(self.scores)
            final_message = f"\nInterview concluded. Your average score is: {average_score:.2f}/10"
        else:
            final_message = "\nInterview concluded. No scores were recorded."

        print(final_message)
        self.text_to_speech(final_message)
        print("Thank you for using the Enhanced AI Interview Prep App!")
        self.text_to_speech("Thank you for using the Enhanced AI Interview Prep App!")
        
        # Here you could add more detailed evaluation if desired
        
        return

if __name__ == "__main__":
    interview_app = AIInterviewPrep()
    interview_app.run_interview()
