# models.py
from extensions import db

class ScheduledPosts(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    scheduled_time = db.Column(db.DateTime, nullable=False)
    post_data = db.Column(db.PickleType, nullable=False)
    posted = db.Column(db.Boolean, default=False)