import streamlit as st
import requests
import tempfile
import time
import os
import google.generativeai as genai
from streamlit_mic_recorder import mic_recorder
from pydub import AudioSegment
from pydub.utils import which

AudioSegment.converter = which("ffmpeg")


# ---- Configuration ----
ASSEMBLY_API = st.secrets["ASSEMBLY_API"]
GEMINI_API = st.secrets["GEMINI_API"]

base_url = "https://api.assemblyai.com"
headers = {"authorization": ASSEMBLY_API}
genai.configure(api_key=GEMINI_API)

# ---- Functions ----
def upload_audio(file_path):
    with open(file_path, "rb") as f:
        response = requests.post(base_url + "/v2/upload", headers=headers, data=f)
    return response.json()["upload_url"]

def transcribe_audio(upload_url):
    data = {"audio_url": upload_url, "language_detection": True}
    url = base_url + "/v2/transcript"
    response = requests.post(url, json=data, headers=headers)
    transcript_id = response.json()['id']
    polling_endpoint = base_url + "/v2/transcript/" + transcript_id

    while True:
        transcription_result = requests.get(polling_endpoint, headers=headers).json()
        if transcription_result['status'] == 'completed':
            return transcription_result
        elif transcription_result['status'] == 'error':
            raise RuntimeError(f"Transcription failed: {transcription_result['error']}")
        else:
            time.sleep(3)

def trim_audio(filename, words_info):
    audio = AudioSegment.from_file(filename)
    clips_dir = tempfile.mkdtemp()
    start_time = 0
    end_time = 0
    segment_count = 0

    for i in words_info:
        if (end_time // 1000) - (start_time // 1000) > 30:
            cropped = audio[start_time:end_time]
            cropped.export(f"{clips_dir}/clip_{segment_count}.mp3", format="mp3")
            start_time = end_time
            segment_count += 1
        end_time = i["end"]

    cropped = audio[start_time:end_time]
    cropped.export(f"{clips_dir}/clip_{segment_count}.mp3", format="mp3")
    return clips_dir

def generate_summary(text, language="english"):
    if language == "english":
        query = f"""This is a Transcript of a discussion on a topic related to Science or Maths. According to the content, you need to tell me 3 things
            1. What is the summary of the text?
            2. What are some important topics or points or formulas covered in the text?
            3. Is there any discussion of an upcoming assignment or a homework? If yes, do tell the important dates.
            Give answers in 3 different paragraph in ENGLISH and do not give any introduction or conclusion
            the content:
            {text}"""
    else:
        query = f"""This is a Transcript of a discussion on a topic related to Science or Maths. According to the content, you need to tell me 3 things
            1. What is the summary of the text?
            2. What are some important topics or points or formulas covered in the text?
            3. Is there any discussion of an upcoming assignment or a homework? If yes, do tell the important dates.
            Give answers in 3 different paragraph in HINDI and do not give any introduction or conclusion
            the content:
            {text}"""

    model = genai.GenerativeModel(model_name="gemini-2.0-flash")
    response = model.generate_content(query)
    return response.text

# ---- Streamlit App ----
st.title("Audio Transcript and Summary App")

input_method = st.radio("Choose input method:", ("Upload MP3", "Record Audio"))

if input_method == "Upload MP3":
    uploaded_file = st.file_uploader("Upload your MP3 file", type=["mp3"])
    if uploaded_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            tmp_file.write(uploaded_file.read())
            audio_file_path = tmp_file.name

elif input_method == "Record Audio":
    audio_file = st.audio_input("Record your audio")

    if audio_file is not None:
        # Save to a temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            tmp_file.write(audio_file.read())
            audio_file_path = tmp_file.name

                # Now you can continue to transcribe and process
                # transcription_result = transcribe_audio(audio_file_path)


if 'audio_file_path' in locals():
    st.audio(audio_file_path)

    if st.button("Start Processing"):
        with st.spinner("Uploading and transcribing..."):
            upload_url = upload_audio(audio_file_path)
            transcription_result = transcribe_audio(upload_url)
            st.success("Transcription completed!")

        st.subheader("Transcript Text")
        st.write(transcription_result["text"])

        with st.spinner("Creating audio clips..."):
            clips_dir = trim_audio(audio_file_path, transcription_result["words"])
        st.success("Audio clips created!")

        st.subheader("Audio Clips")
        for clip_file in sorted(os.listdir(clips_dir)):
            clip_path = os.path.join(clips_dir, clip_file)
            st.audio(clip_path)

        with st.spinner("Generating summaries..."):
            summary_en = generate_summary(transcription_result["text"], language="english")
            summary_hi = generate_summary(transcription_result["text"], language="hindi")
        st.success("Summaries generated!")

        st.subheader("Summary in English")
        st.write(summary_en)

        st.subheader("Summary in Hindi")
        st.write(summary_hi)
