import asyncio
import json
import os
from dotenv import load_dotenv
from livekit import api
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import cartesia, deepgram, openai, silero

load_dotenv()

OUTBOUND_TRUNK_ID = os.getenv("LIVEKIT_OUTBOUND_TRUNK_ID")  # Your Kenyan SIP Outbound Trunk ID

class KenyanTutor(Agent):
    def __init__(self, student_phone: str) -> None:
        super().__init__(
            instructions=(
                "You are a friendly Kenyan AI tutor. You just called the student back "
                "after they flashed your number. Follow the Kenyan CBC and KCSE syllabus "
                "and keep your answers short and clear for a phone call."
            )
        )
        self.student_phone = student_phone

async def trigger_callback(student_phone: str):
    """Dials the student back in a fresh LiveKit room."""
    await asyncio.sleep(2)  # Give the student's phone 2 seconds to clear the missed call

    lkapi = api.LiveKitAPI()
    callback_room = f"tutor-callback-{student_phone.replace('+', '')}"

    try:
        await lkapi.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                sip_trunk_id=OUTBOUND_TRUNK_ID,
                sip_call_to=student_phone,
                room_name=callback_room,
                participant_identity=f"student-{student_phone}",
                participant_name="Kenyan Student",
                play_ringtone=True,
            )
        )
    finally:
        await lkapi.aclose()

async def entrypoint(ctx: JobContext):
    await ctx.connect()
    participant = await ctx.wait_for_participant()
    student_phone = participant.attributes.get("sip.phoneNumber")

    # Check if this is an INBOUND flash call (room name starts with 'flash-')
    if ctx.room.name.startswith("flash-") and student_phone:
        print(f"Flash detected from {student_phone}. Hanging up and calling back...")
        
        # 1. Trigger the callback in the background
        asyncio.create_task(trigger_callback(student_phone))
        
        # 2. Immediately delete the inbound room so the student is NOT billed airtime
        lkapi = api.LiveKitAPI()
        await lkapi.room.delete_room(api.DeleteRoomRequest(room=ctx.room.name))
        await lkapi.aclose()
        return

    # Otherwise, this is the OUTBOUND callback room—start the AI tutor!
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-2", language="en"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=cartesia.TTS(model="sonic-2"),
    )

    await session.start(room=ctx.room, agent=KenyanTutor(student_phone))
    await session.generate_reply(
        instructions="Say hello, let them know this is their free callback from the AI tutor, and ask what subject they want to revise."
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
