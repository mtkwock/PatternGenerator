import math

from dataclasses import dataclass
from dataclasses import replace as CopyDataclass
from proto import spawner_pb2
from typing import Callable
import random

_FUNCTIONS = {
  'sin': math.sin,
  'cos': math.cos,
  'log': math.log,
  'math': math,
  'r': random,
}

_CONSTANTS = {
  'e': math.e,
  'pi': math.pi,
  'tau': math.tau,
}

_GLOBALS = _FUNCTIONS | _CONSTANTS

def GetGlobals() -> dict:
  return _GLOBALS.copy()

def MakeFn(expr: str) -> Callable[[dict[str, float]], float]:
  """Create a function from the string to be evaluated with ctx globals.

  Currently, this is implemented as an eval with limited ctx scope.
  """
  # TODO: Sanitize expr before using it in eval if this ever goes
  # beyond a toy phase.  This is a dangerous possibility of Arbitrary
  # Code Execution.
  expr = compile(expr, '', 'eval')
  return lambda ctx: eval(expr, ctx, {})

DEFAULT_STATE_FN = lambda _: 0

"""
Some notes regarding context and variables that need to be passed.

We need the following values:

t: Time since spawn
dt: Time since last update
x: Entity's current x position
y: Entity's current y position
o: Entity's current Angle (in radians)
"""

@dataclass
class PositionState:
  """A Dataclass holding Entity State."""
  x: float = 0
  y: float = 0
  angle: float = 0

  def Add(self, other: 'PositionState') -> 'PositionState':
    return PositionState(
      self.x + other.x,
      self.y + other.y,
      self.angle + other.angle,
    )

  def __add__(self, other: 'PositionState') -> 'PositionState':
    return PositionState(
      self.x + other.x,
      self.y + other.y,
      self.angle + other.angle,
    )    

  def __radd__(self, other: 'PositionState') -> 'PositionState':
    return PositionState(
      self.x + other.x,
      self.y + other.y,
      self.angle + other.angle,
    )    

  def __eq__(self, other: 'PositionState') -> bool:
    return (
      math.isclose(self.x, other.x) and 
      math.isclose(self.y, other.y) and
      math.isclose(self.angle, other.angle))

@dataclass
class CompiledStateFn:
  """A dataclass holding functions to determine the next state.

  These functions take a dictionary of variables and compute them.
  """
  x: Callable[[dict[str, float]], float] = DEFAULT_STATE_FN
  y: Callable[[dict[str, float]], float] = DEFAULT_STATE_FN
  angle: Callable[[dict[str, float]], float] = DEFAULT_STATE_FN

  def Calc(self, ctx: dict[str, float]) -> PositionState:
    global_vars = _GLOBALS | ctx
    return PositionState(
      self.x(global_vars),
      self.y(global_vars),
      self.angle(global_vars))

DEFINED_FUNCTIONS_: dict[str, CompiledStateFn] = {}

def ClearDefinedFunctions():
  DEFINED_FUNCTIONS_.clear()

def GenerateCartesianStateFn(
    cartesian_pb: spawner_pb2.CartesianStateFn,
    save: bool = False) -> CompiledStateFn:
  """Generates a CompiledStateFn from the given Cartesian function.

  Optionally stores this for later use if save is set to True.

  x, y, and angle default to being 0.

  Returns:
    CompiledStateFn with x, y, and and angle filled from Cartesian coordinates.
  Raises:
    FailedPreconditionException: if trying to store without id.
  """
  res = CompiledStateFn()
  if cartesian_pb.x:
    res.x = MakeFn(cartesian_pb.x)
  if cartesian_pb.y:
    res.y = MakeFn(cartesian_pb.y)
  if cartesian_pb.angle:
    res.angle = MakeFn(cartesian_pb.angle)

  if save:
    if not cartesian_pb.id.id:
      raise Exception(f'No id defined to store: {cartesian_pb}')
    DEFINED_FUNCTIONS_[cartesian_pb.id.id] = res
  return res

def GeneratePolarStateFn(
    polar_pb: spawner_pb2.PolarStateFn,
    save: bool = False) -> CompiledStateFn:
  """Generates a CompiledStateFn from the given Polar functions.

  Optionally stores this for later use if save is set to True.
  Note that the final functions are converted to cartesian definitions.

  ie.
    x = rcos(theta)
    y = rsin(theta)

  Note that theta, and r default to 0 if not defined.

  Returns:
    CompiledStateFn with x, y, and and angle filled from Cartesian coordinates.
  Raises:
    FailedPreconditionException: if trying to store without id.
  """
  res = CompiledStateFn()
  r_str = polar_pb.r or '0'
  theta_str = polar_pb.theta or '0'
  x_str = f'({r_str}) * cos({theta_str})'
  y_str = f'({r_str}) * sin({theta_str})'

  res.x = MakeFn(x_str)
  res.y = MakeFn(y_str)
  if polar_pb.angle:
    res.angle = MakeFn(polar_pb.angle)
  if save:
    if not polar_pb.id.id:
      raise Exception(f'No id defined to store: {polar_pb}')
    DEFINED_FUNCTIONS_[polar_pb.id.id] = res
  return res

def GenerateDeltaStateFn(
    delta_pb: spawner_pb2.DeltaStateFn,
    save: bool = False) -> CompiledStateFn:
  """Generates a CompiledStateFn from the given Delta functions.

  Optionally stores this for later use if save is set to True.
  Note that the final functions are converted to cartesian definitions.

  e.g.
    x = x + dx * dt
    y = y + dy * dt
    angle = angle + w * dt

  Note that dx, dy, and w default to 0 if not defined.

  Returns:
    CompiledStateFn with x, y, and and angle filled from Cartesian coordinates.
  Raises:
    FailedPreconditionException: if trying to store without id.
  """
  res = CompiledStateFn()
  x_str = 'x';
  y_str = 'y';
  angle_str = 'angle';
  if delta_pb.dx:
    res.x = MakeFn(f'x + ({delta_pb.dx}) * dt')
  if delta_pb.dy:
    res.y = MakeFn(f'y + ({delta_pb.dy}) * dt')
  if delta_pb.w:
    res.angle = MakeFn(f'angle + ({delta_pb.w}) * dt')

  if save:
    if not delta_pb.id.id:
      raise Exception(f'No id defined to store: {delta_pb}')
    DEFINED_FUNCTIONS_[delta_pb.id.id] = res
  return res


def GenerateCompiledStateFn(state_fn_pb: spawner_pb2.StateFn) -> CompiledStateFn:
  """Generate a CompiledStateFn from the StateFn wrapper.

  This can either access a previously defined function or be one of the
  defined StateFn alternatives.
  """
  if state_fn_pb.id.id:
    # Fetch existing ID if it exists, else throw Error
    if state_fn_pb.id.id not in DEFINED_FUNCTIONS_:
      raise Exception(f"Expected predefined StateFn for id: {state_fn_pb.id.id}")
    return CopyDataclass(DEFINED_FUNCTIONS_[state_fn_pb.id.id])
  elif state_fn_pb.HasField('cartesian'):
    return GenerateCartesianStateFn(state_fn_pb.cartesian)
  elif state_fn_pb.HasField('polar'):
    return GeneratePolarStateFn(state_fn_pb.polar)
  elif state_fn_pb.HasField('delta'):
    return GenerateDeltaStateFn(state_fn_pb.delta)
  else:
    raise Exception("StateFn does not have any function set.")
