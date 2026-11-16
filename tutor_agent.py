import os
from dotenv import load_dotenv
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import cartesia, deepgram, openai, silero

load_dotenv()

class KenyanTutor(Agent):
    def __init__(self, student_phone: str) -> None:
        super().__init__(
            instructions=(
                "You are a friendly, patient Kenyan tutor helping a student via a phone call. "
                "Follow the Kenyan CBC and KCSE syllabus. Keep answers concise, clear, and "
                "easy to follow over audio—avoid long lists or complex formatting. "
                "Ask one check-in question at a time to keep the student engaged."
            )
        )
        self.student_phone = student_phone

async def entrypoint(ctx: JobContext):
    # Connect to the LiveKit room created by the incoming SIP call
    await ctx.connect()

    # Wait for the student (SIP participant) to join and grab their +254 caller ID
    participant = await ctx.wait_for_participant()
    student_phone = participant.attributes.get("sip.phoneNumber", "Unknown")
    print(f"Student connected from: {student_phone}")

    # Configure the low-latency voice pipeline
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-2", language="en"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=cartesia.TTS(model="sonic-2"),
    )

    # Start the AI tutor and greet the student immediately
    await session.start(room=ctx.room, agent=KenyanTutor(student_phone))
    await session.generate_reply(
        instructions="Greet the student warmly and ask what subject or topic they want to revise today."
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
