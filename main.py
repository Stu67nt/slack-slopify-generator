import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
import edge_tts
import asyncio
from moviepy import VideoFileClip, vfx, AudioFileClip
import re
import random
import threading

load_dotenv()
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

@app.event("message")
def handle_message_events(ack):
	# Just acknowledge the event so Bolt stops complaining
	ack()

def handle_mention(event, client, say):
	print("Recieved: " + event["text"])
	channel_id = event.get("channel")
	thread_ts = event.get("thread_ts")
	user_id = event.get("user")

	if "slopify" not in event["text"].split():
		print("No slopify")
		return
	if not thread_ts:
		client.chat_postEphemeral(
			channel=channel_id,
			user=user_id,  # ID of the user who should see the message
			thread_ts=thread_ts,  # Keeps the ephemeral message inside the thread
			text="Mention me inside of the thread you want to slopify"
		)
		return

	result = client.conversations_replies(channel=event["channel"], ts=thread_ts)
	messages = result.get("messages", [])
	return messages, thread_ts, user_id

async def speak(text, name="output"):
	communicate = edge_tts.Communicate(text)
	await communicate.save(f"{name}.mp3")

def upload_video(client, user_id, file_path, thread_ts):
	dm = client.conversations_open(users=user_id)
	dm_channel_id = dm["channel"]["id"]
	client.files_upload_v2(
		channel=dm_channel_id,  # DMs to the user directly
		file=file_path,
		title=f"Slopified video {thread_ts}"
	)
	os.remove(f"{thread_ts}.mp4")

@app.event("app_mention")
def handle_slop_mention(event, client, say):
	messages, thread_ts, user_id = handle_mention(event, client, say)
	text = ""
	for message in messages:
		p = r'https?://\S+|www\.\S+'
		n_url = str(re.sub(p, "", message["text"]))
		parts = re.split(r"<@(U[A-Z0-9]+)>", n_url)
		for i in range(0, len(parts)):
			if re.match(r"U[A-Z0-9]+", parts[i]):
				parts[i] = client.users_info(user=parts[i])["user"]["profile"]["display_name"]
		msg = "".join(parts)
		text += msg+". "

	print("turning to audio")
	asyncio.run(speak(text, thread_ts))

	print("turing to video")
	audio_clip = AudioFileClip(f"{thread_ts}.mp3")

	mypath = "slop_videos"
	onlyfiles = [f for f in os.listdir(mypath) if os.path.isfile(os.path.join(mypath, f))]
	file_i = random.randint(0, len(onlyfiles) - 1)

	video_clip = (
		VideoFileClip(f"{mypath}/{onlyfiles[file_i]}")
		.with_volume_scaled(0)
	).with_effects([vfx.Loop(duration=audio_clip.duration)])

	video_clip.audio = audio_clip.subclipped(0, video_clip.duration)
	video_clip.write_videofile(f"{thread_ts}.mp4")
	os.remove(f"{thread_ts}.mp3")

	threading.Thread(target=upload_video, args=(client, user_id, f"{thread_ts}.mp4", thread_ts)).start()


if __name__ == "__main__":
	SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()

