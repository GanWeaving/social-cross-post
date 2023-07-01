from app import app, ScheduledPosts

def get_all_scheduled_posts():
    with app.app_context():
        scheduled_posts = ScheduledPosts.query.all()
        return scheduled_posts

all_posts = get_all_scheduled_posts()

if len(all_posts) == 0:
    print("No scheduled posts found in the database.")
else:
    print(f"Number of scheduled posts: {len(all_posts)}")
    for post in all_posts:
        print(f"Post ID: {post.id}")
        print(f"Text: {post.text}")
        print(f"Scheduled Time: {post.scheduled_time}")
        print(f"Post Data: {post.post_data}")
        print(f"Posted? {post.posted}")
        print()
