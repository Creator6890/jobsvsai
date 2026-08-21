import os

from redis import Redis
from rq import Queue, Worker


def main() -> None:
    redis = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    queue = Queue(os.getenv("QUEUE_NAME", "default"), connection=redis)
    Worker([queue], connection=redis).work(with_scheduler=False)


if __name__ == "__main__":
    main()
