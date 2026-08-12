import asyncio
import uuid
import os
from app.models.video import VideoCreateRequest, JobStatus
from app import jobs

os.environ['USE_DEMO_MODE'] = 'true'

req = VideoCreateRequest(
    prompt='Test backend video generation',
    duration=15,
    aspect_ratio='9:16',
    style='Cinematic',
    voice='Neutral',
    language='English',
    captions_enabled=True,
    background_music=False,
)
job_id = uuid.uuid4().hex[:12]
jobs.JOBS[job_id] = JobStatus(job_id=job_id, status='queued', stage='Queued', progress=0)
print('job', job_id)
try:
    asyncio.run(jobs.run_video_pipeline(job_id, req))
except Exception as exc:
    import traceback
    traceback.print_exc()
print('status', jobs.get_job(job_id).model_dump())
