from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pid = db.Column(db.Integer, nullable=True, unique=True)  # real OS process ID
    name = db.Column(db.String(120), nullable=False)
    priority = db.Column(db.String(20), nullable=False, default='Medium')  # High/Medium/Low
    status = db.Column(db.String(20), nullable=False, default='Pending')  # Pending/Running/Paused/Completed

    arrival_time = db.Column(db.DateTime, default=datetime.utcnow)
    burst_time = db.Column(db.Integer, default=5)     # simulated execution time
    remaining_time = db.Column(db.Integer, default=5)
    deadline = db.Column(db.DateTime, nullable=True)
    progress = db.Column(db.Integer, default=0)       # New field for progress %
    energy = db.Column(db.Integer, default=100)       # New field for energy %
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    type = db.Column(db.String(20), default='simulated')  # distinguish real/simulated 
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    locked = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<Task id={self.id} name={self.name} pid={self.pid} status={self.status} progress={self.progress}>"

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'))
    decision = db.Column(db.String(20))
    battery = db.Column(db.Float, default=0)
    cpu = db.Column(db.Float, default=0)
    outcome = db.Column(db.String(20))
    
    # Additional fields
    message = db.Column(db.String(255), nullable=True)        # Text of the log
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)  # Auto timestamp

    def __repr__(self):
        return f"<Log id={self.id} task_id={self.task_id} decision={self.decision}>"
    
    
