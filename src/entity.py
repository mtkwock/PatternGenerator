
from proto import spawner_pb2
from google.protobuf import text_format
from src.state_function import CompiledStateFn
from src.state_function import GenerateCompiledStateFn
from src.state_function import GetGlobals
from src.state_function import MakeFn
from src.state_function import PositionState
from dataclasses import dataclass
from dataclasses import replace as CopyDataclass
from typing import Optional
import logging
from math import sin, cos
from typing import Optional

GLOBALS_ = GetGlobals()

class Movement():
  def __init__(self, movement_pb: spawner_pb2.Movement):
    self.movement_pb_: spawner_pb2.Movement
    self.state_fns: list[CompiledStateFn] = [
        GenerateCompiledStateFn(state_fn)
        for state_fn in movement_pb.state_fn]
    assert self.state_fns, "Needs at least one specified movement!"
    self.loop = movement_pb.loop or False

    self.lifetimes = list(movement_pb.lifetime)

    assert len(self.state_fns) == len(self.lifetimes), 'Movements and Lifetimes lengths must match! ${movement_pb}'

    # Which movement to use.
    # If current_idx is above state_fns.length and loops, resets to 0
    # If not looping, is_active will be set to False
    self.current_idx = 0
    self.current_time = 0
    self.is_active = True

    # Transitional position at the edges of state_fn.
    # This should be fetched and cleared before Calc is called again.
    self.transition_position_: Optional[PositionState] = None

  def Calc(self, fn_vars: dict[str, float], dt: float) -> Optional[PositionState]:
    if self.transition_position_:
      raise Exception("Trying to Calculate new state without first calling GetAndClearTransitionPosition")
    next_time = self.current_time + dt
    lifetime = self.lifetimes[self.current_idx]
    # self.current_time += dt
    # Handle end of lifetime for current movement. Only applicable if lifetime > 0
    if (lifetime > 0 and next_time > lifetime):
      # Handle transitions by pushing towards the end of the lifetime and
      # Storing the final position temporarily.
      first_dt = lifetime - self.current_time
      state_fn = self.state_fns[self.current_idx]
      transition_globals = fn_vars | {'t': lifetime, 'dt': first_dt}
      self.transition_position_ = state_fn.Calc(transition_globals)

      # The remaining dt to be used
      dt = next_time - lifetime

      self.current_time = dt
      self.current_idx += 1
      if (self.current_idx >= len(self.state_fns)):
        if self.loop:
          self.current_idx = 0
        # Reached end of loop, we should no longer be active or returning anything.
        else:
          self.is_active = False
          return None
    else:
      self.current_time = next_time
    state_fn = self.state_fns[self.current_idx]
    passed_globals = fn_vars | {'t': self.current_time, 'dt': dt}
    return state_fn.Calc(passed_globals)

  def GetAndClearTransitionPosition(self) -> Optional[PositionState]:
    """Readies this movement to be Calc'd again after state_fn transitions

    When Calc is called and dt causes a transition between state_fn,
    we get into a wonky state that needs to update the State Offset.

    If we do not handle this offset, we can get weird behaviors because
    the new "center" hasn't been updated. To get around this, we're storing the
    position at the end of the lifetime and holding that for the containing
    Entity to update its offset with before using the next positional data.

    Calling this allows one-time access to transition_position_, allowing further
    calls to Calc to happen.
    """
    res = self.transition_position_
    self.transition_position_ = None
    return res

WORLD_PB_TXT = """
  id { id: 'world' }
  image: ''
  movement {
    state_fn { cartesian {} }
    lifetime: 0
    loop: true
  }
"""
WORLD_ENTITY_PB = text_format.Parse(WORLD_PB_TXT, spawner_pb2.Entity())

class Entity():
  SAVED_: dict[str, spawner_pb2.Entity] = {
    'world': WORLD_ENTITY_PB,
  }
  ZA_WARUDO: 'Entity'

  @classmethod
  def Save(cls, entity_pb: spawner_pb2.Entity):
    name = entity_pb.id.id
    if not name:
      raise Exception('No entity_pb id value set when trying to save.')
    if name in Entity.SAVED_:
      logging.warn(f'Entity already defined for id: {name} - Not creating')
    else:
      cls.SAVED_[name] = entity_pb    

  def __init__(self,
      entity_pb: spawner_pb2.Entity,
      parent: 'Entity' = None,
      offset: PositionState = None,
      idx: int = 0,
      follow_center: bool = False,
      follow_angle: bool = False):
    self.pb_ = entity_pb
    name = entity_pb.id.id
    if name:
      if name in Entity.SAVED_:
        self.pb_ = spawner_pb2.Entity()
        self.pb_.CopyFrom(Entity.SAVED_[name])
      else:
        logging.warn(f'Trying to load nonexistent entity: "{name}", using protobuf definition.')

    self.image: str = self.pb_.image
    self.hit_radius = self.pb_.hit_radius
    self.alignment = self.pb_.alignment

    # The parent 
    self.parent: Optional[Entity] = parent
    self.follow_center = follow_center
    self.follow_angle = follow_angle
    self.idx = idx

    # Spawners to create children
    self.spawners: list['Spawner'] = []
    for spawner_pb in self.pb_.spawner:
      self.spawners.append(Spawner(spawner_pb, self))

    # The children
    self.children_: list[Entity] = []

    # Positional Fields
    self.movement = Movement(self.pb_.movement)
    # positional data relative to the parent.
    # If no parent, the absolute center.
    self.offset: PositionState = offset or PositionState()
    self.position = PositionState()
    self.recalc_absolute_ = True
    self.absolute_position_ = self.AbsolutePosition()

  def AddChild(self, child: 'Entity'):
    self.children_.append(child)

  def UpdateSpawners_(self, global_vals: dict[str, float], dt: float):
    for spawner in self.spawners:
      spawner.Update(global_vals, dt)
 
  def UpdateChildren_(self, global_vals: dict[str, float], dt: float):
    for child in self.children_:
      if not child.movement.is_active:
        self.children_.remove(child)
        continue
      child.Update(global_vals, dt)

  def UpdatePosition_(self, global_vals: dict[str, float], dt: float):
    absolute = self.AbsolutePosition()
    vals = {
      'x':     self.position.x,
      'y':     self.position.y,
      'angle': self.position.angle,
      'idx':   self.idx,
      'xa':     absolute.x,
      'ya':     absolute.y,
      'anglea': absolute.angle,
    }
    self.position = self.movement.Calc(global_vals | vals, dt)
    if not self.position:
      # TODO: Handle empty?
      self.position = PositionState(0, 0, 0)
    # Handle state_fn transitions
    transition_position = self.movement.GetAndClearTransitionPosition()
    if transition_position:
      self.offset += transition_position

    self.recalc_absolute_ = True

  def Update(self, global_vals: dict[str, float], dt: float):
    self.UpdateSpawners_(global_vals, dt)
    self.UpdateChildren_(global_vals, dt)
    self.UpdatePosition_(global_vals, dt)

  def AbsolutePosition(self) -> PositionState:
    """Get the absolute position using relevant info from parents

    When calculated once, stores the value dynamically until
    result is marked dirty by an Update.

    parent's absolute position
      xp, yp, anglep

    Offset from parent's position "CENTER"
      xo, yo, angleo

    Calculated Position relative to center
      x, y, angle

    Centered Position relative to "CENTER"
      xc = x + xo
      yc = y + yo
      anglec = angle + angleo

    Absolute Position Following center But not angle
      xc + xp
      xy + yp
      angle + angleo

    Absolute Position Following center AND angle
      xp + xc * cos(anglep) + yc * sin(anglep)
      yp - xc * sin(anglep) + yc * cos(anglep)
      angle + angleo + anglep
    """
    if not self.recalc_absolute_:
      return self.absolute_position_
    centered = self.position + self.offset
    if not self.parent:
      self.absolute_position_ = centered
      return centered

    parent = CopyDataclass(self.parent.AbsolutePosition())

    # Position relative to the center not accounting for parent.
    if self.follow_center and self.follow_angle:
      transformed = PositionState(
        parent.x + centered.y * sin(parent.angle) + centered.x * cos(parent.angle),
        parent.y + centered.y * cos(parent.angle) - centered.x * sin(parent.angle),
        parent.angle + centered.angle
      )
    elif self.follow_center and not self.follow_angle:
      transformed = PositionState(
        parent.x + centered.x,
        parent.y + centered.y,
        centered.angle,
      )
    elif self.follow_angle:
      transformed = PositionState(
        centered.y * sin(parent.angle) + centered.x * cos(parent.angle),
        centered.y * cos(parent.angle) - centered.x * sin(parent.angle),
        centered.angle + parent.angle,
      )
    else:
      transformed = CopyDataclass(centered)

    self.absolute_position_ = transformed
    self.recalc_absolute_ = False
    return self.absolute_position_

Entity.ZA_WARUDO = Entity(WORLD_ENTITY_PB)

class Spawner():
  SAVED_: dict[str, spawner_pb2.Spawner] = {}

  @classmethod
  def Save(cls, spawner_pb: spawner_pb2.Spawner):
    name = spawner_pb.id.id
    if not name:
      raise Exception('Cannot save Spawner without an id')
    if name in Spawner.SAVED_:
      logging.warn(f'Spawner already defined: {name} - Not creating')
    else:
      Spawner.SAVED_[name] = spawner_pb

  def __init__(self,
      spawner_pb: spawner_pb2.Spawner,
      parent: Optional[Entity] = None):
    self.spawner_pb_ = spawner_pb

    name = spawner_pb.id.id
    if name:
      if name in Spawner.SAVED_:
        self.spawner_pb_ = Spawner.SAVED_[name]
      else:
        logging.warn(f'Spawner not defined for id {name}, defaulting to using proto.')

    self.spawned_entity_pb_ = self.spawner_pb_.spawn_entity

    self.follow_center = parent and self.spawner_pb_.follow_center
    self.follow_angle = parent and self.spawner_pb_.follow_angle
    self.parent = parent if self.follow_center or self.follow_angle else None
    if not self.spawner_pb_.HasField('offset_fn'):
      self.spawner_pb_.offset_fn.cartesian.x = '0'
    self.offset_fn_ = GenerateCompiledStateFn(self.spawner_pb_.offset_fn)

    self.spawn_count = self.spawner_pb_.spawn_count
    self.spawn_time_fn = MakeFn(self.spawner_pb_.spawn_time_fn)
    # These are ordered times to spawn and indexes to spawn at.
    self.zipped_spawn_times_idx: list[tuple[float, int]] = []
    self.period = self.spawner_pb_.period or 0
    self.InitializeSpawnTimes()

    self.current_time = 0
    self.current_spawn_pos = 0

  def InitializeSpawnTimes(self):
    result = []
    for i in range(self.spawn_count):
      # TODO: Consider passing parent information?
      global_vals = GLOBALS_ | {'idx': i, 'parent': self.parent}
      spawn_time = self.spawn_time_fn(global_vals)
      result.append((spawn_time, i))
    self.zipped_spawn_times_idx = sorted(result, key=lambda pair: pair[0])

  def Update(self, global_vals: dict[str, float], dt: float):
    next_time = self.current_time + dt

    # Time has passed over the spawn time, 
    while (self.current_spawn_pos < self.spawn_count and 
      next_time > self.zipped_spawn_times_idx[self.current_spawn_pos][0]):
      t, idx = self.zipped_spawn_times_idx[self.current_spawn_pos]
      local_vals = { 't': t, 'idx': idx }

      spawn = Entity(
        self.spawned_entity_pb_,
        self.parent,
        self.offset_fn_.Calc(global_vals | local_vals),
        idx, # idx
        self.follow_center,
        self.follow_angle
      )

      if self.parent:
        self.parent.AddChild(spawn)
      else:
        Entity.ZA_WARUDO.AddChild(spawn)

      self.current_spawn_pos += 1

    self.current_time = next_time

    if self.period > 0 and next_time >= self.period:
      self.current_time = next_time - self.period
      self.current_spawn_pos = 0
