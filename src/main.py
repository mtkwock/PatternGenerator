import pygame
from queue import Queue
import time

from proto.spawner_pb2 import Entity
from proto import spawner_pb2
from google.protobuf import text_format
from src.state_function import GenerateCartesianStateFn
from src.state_function import GenerateDeltaStateFn
from src.state_function import GeneratePolarStateFn
from src.state_function import GetGlobals
from src.entity import Entity
from src.entity import Spawner

# https://stackoverflow.com/a/77572870
# from rules_python.python.runfiles import runfiles
from python.runfiles import Runfiles

GLOBALS_ = GetGlobals()

def TestEntityLoad():
  resource = "__main__/src/my_first_entity.textproto"
  r = Runfiles.Create()

  print(r.Rlocation(resource))

  with open(r.Rlocation(resource), 'r') as f:
  	e = Entity()
  	text_format.Parse(f.read(), e)

  	print(e.movement)

def LoadDefinedUnits(resource: str):
  r = Runfiles.Create()
  with open(r.Rlocation(resource), 'r') as f:
    defined = text_format.Parse(f.read(), spawner_pb2.DefinedUnits())

    for cartesian_pb in defined.cartesian_function:
      GenerateCartesianStateFn(cartesian_pb, True)
    for polar_pb in defined.polar_function:
      GeneratePolarStateFn(polar_pb, True)
    for delta_pb in defined.delta_function:
      GenerateDeltaStateFn(delta_pb, True)

    for entity_pb in defined.entity:
      Entity.Save(entity_pb)

    for spawner_pb in defined.spawner:
      Spawner.Save(spawner_pb)

def LoadSun():
  sun_pb = spawner_pb2.Entity()
  sun_pb.id.id = 'sun'
  sun = Entity(sun_pb)

  Entity.ZA_WARUDO.AddChild(sun)

def StartPyGameLoop():
  pygame.init()
  screen = pygame.display.set_mode((1280, 720))
  clock = pygame.time.Clock()
  running = True
  current_time = time.time()

  while running:
      # poll for events
      # pygame.QUIT event means the user clicked X to close your window
      for event in pygame.event.get():
          if event.type == pygame.QUIT:
              running = False

      next_time = time.time()
      dt = next_time - current_time
      current_time = next_time
      Entity.ZA_WARUDO.Update(GLOBALS_, dt)

      # fill the screen with a color to wipe away anything from last frame
      screen.fill("black")

      # RENDER YOUR GAME HERE
      to_render = Queue()
      for child in Entity.ZA_WARUDO.children_:
        to_render.put(child)

      while not to_render.empty():
        entity_to_draw = to_render.get()
        pos = entity_to_draw.AbsolutePosition()
        pygame.draw.circle(screen, "red", (pos.x, pos.y), 5)
        for child in entity_to_draw.children_:
          to_render.put(child)

      # flip() the display to put your work on screen
      pygame.display.flip()

      clock.tick(60)  # limits FPS to 60

  pygame.quit()

def Main():
  resource = "__main__/src/simple_solar_system.textproto"
  LoadDefinedUnits(resource)
  LoadSun()
  StartPyGameLoop()


if __name__ == '__main__':
  Main()