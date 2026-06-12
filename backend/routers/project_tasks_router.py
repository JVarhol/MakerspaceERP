from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from ..database import get_db
from ..models import ProjectTask, Project, ProjectShare
from .. import auth

router = APIRouter(prefix="/api/project-tasks", tags=["project-tasks"])

_R = Depends(auth.get_current_user)


# ── Schemas ───────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    project_id:  int
    title:       str
    description: Optional[str]  = None
    status:      Optional[str]  = "todo"
    priority:    Optional[str]  = "normal"
    assignee:    Optional[str]  = None
    team_id:     Optional[int]  = None
    due_date:    Optional[str]  = None
    color:       Optional[str]  = None
    position:    Optional[int]  = 0
    created_by:  Optional[str]  = None
    checklist:   Optional[str]  = None

class TaskUpdate(BaseModel):
    title:       Optional[str]  = None
    description: Optional[str]  = None
    status:      Optional[str]  = None
    priority:    Optional[str]  = None
    assignee:    Optional[str]  = None
    team_id:     Optional[int]  = None
    due_date:    Optional[str]  = None
    color:       Optional[str]  = None
    position:    Optional[int]  = None
    checklist:   Optional[str]  = None

class TaskPositionItem(BaseModel):
    id:       int
    status:   str
    position: int


def _task_out(t: ProjectTask) -> dict:
    return {
        "id":          t.id,
        "project_id":  t.project_id,
        "title":       t.title,
        "description": t.description,
        "status":      t.status,
        "priority":    t.priority,
        "assignee":    t.assignee,
        "team_id":     t.team_id,
        "team_name":   t.team.name if t.team else None,
        "due_date":    t.due_date,
        "color":       t.color,
        "position":    t.position,
        "created_by":  t.created_by,
        "checklist":   t.checklist,
        "created_at":  t.created_at.isoformat() if t.created_at else None,
        "updated_at":  t.updated_at.isoformat() if t.updated_at else None,
    }


def _check_project_access(project_id: int, cu, db: Session):
    """Raise 403 unless cu is admin, project assignee, or a project share member."""
    if cu.role == "admin":
        return
    proj = db.get(Project, project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    if proj.assigned_to == cu.username:
        return
    share = db.query(ProjectShare).filter(
        ProjectShare.project_id == project_id,
        ProjectShare.username == cu.username,
    ).first()
    if not share:
        raise HTTPException(403, "Access denied to this project")


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("")
def list_tasks(project_id: Optional[int] = None, status: Optional[str] = None,
               _cu=_R, db: Session = Depends(get_db)):
    q = db.query(ProjectTask)
    if project_id is not None:
        _check_project_access(project_id, _cu, db)
        q = q.filter(ProjectTask.project_id == project_id)
    elif _cu.role != "admin":
        # Non-admins see only tasks from projects they own or share
        owned  = db.query(Project.id).filter(Project.assigned_to == _cu.username)
        shared = db.query(ProjectShare.project_id).filter(ProjectShare.username == _cu.username)
        q = q.filter(ProjectTask.project_id.in_(owned.union(shared)))
    if status:
        q = q.filter(ProjectTask.status == status)
    return [_task_out(t) for t in q.order_by(ProjectTask.status, ProjectTask.position).all()]


@router.post("", status_code=201)
def create_task(data: TaskCreate, _cu=_R, db: Session = Depends(get_db)):
    _check_project_access(data.project_id, _cu, db)
    t = ProjectTask(**data.model_dump())
    db.add(t); db.commit(); db.refresh(t)
    return _task_out(t)


@router.patch("/{tid}")
def update_task(tid: int, data: TaskUpdate, _cu=_R, db: Session = Depends(get_db)):
    t = db.get(ProjectTask, tid)
    if not t: raise HTTPException(404, "Task not found")
    _check_project_access(t.project_id, _cu, db)
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(t, k, v)
    db.commit(); db.refresh(t)
    return _task_out(t)


@router.delete("/{tid}", status_code=204)
def delete_task(tid: int, _cu=_R, db: Session = Depends(get_db)):
    t = db.get(ProjectTask, tid)
    if not t: raise HTTPException(404, "Task not found")
    _check_project_access(t.project_id, _cu, db)
    db.delete(t); db.commit()


@router.put("/reorder")
def reorder_tasks(items: List[TaskPositionItem], _cu=_R, db: Session = Depends(get_db)):
    """Bulk update status + position for drag-and-drop reordering."""
    for item in items:
        t = db.get(ProjectTask, item.id)
        if t:
            _check_project_access(t.project_id, _cu, db)
            t.status   = item.status
            t.position = item.position
    db.commit()
    return {"ok": True}
