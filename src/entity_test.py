import unittest
import math

from dataclasses import replace as CopyDataclass
from google.protobuf import text_format
from proto import spawner_pb2
from src import entity
from src.state_function import GenerateCartesianStateFn
from src.state_function import PositionState

class MovementTest(unittest.TestCase):
  def testCalc_basicAcceptableMovement_parses(self):
    movement_pb = text_format.Parse("""
        state_fn {
          cartesian {
            x: "2 * t"
            y: "5 * t"
            angle: "t"
          }
        }
        lifetime: 0
      """,
      spawner_pb2.Movement())

    res = entity.Movement(movement_pb)

    self.assertEqual(res.Calc({}, 1.0), PositionState(2.0, 5.0, 1.0))

  def test_noStateFn_throwsAssertionError(self):
    movement_pb = text_format.Parse("""
      lifetime: 0
    """, spawner_pb2.Movement())

    with self.assertRaises(AssertionError):
      res = entity.Movement(movement_pb)

  def test_mismatchedLifetimeStateFnLength_throwsAssertionError(self):
    movement_pb = text_format.Parse("""
        state_fn { cartesian { x: "2 * t" y: "5 * t" angle: "t" } }
        lifetime: 0
        lifetime: 1
        lifetime: 2
      """,
      spawner_pb2.Movement())

    with self.assertRaises(AssertionError):
      res = entity.Movement(movement_pb)

  def testCalc_multipleCalls_increasesLifetimeCalcs(self):
    movement_pb = text_format.Parse("""
        state_fn {
          cartesian {
            x: "2 * t"
            y: "5 * t"
            angle: "t"
          }
        }
        lifetime: 0
      """,
      spawner_pb2.Movement())

    movement = entity.Movement(movement_pb)
    pos_1 = movement.Calc({}, 1)
    pos_2 = movement.Calc({}, 1)
    pos_3 = movement.Calc({}, 1)

    self.assertEqual(pos_1, PositionState(2,  5, 1))
    self.assertEqual(pos_2, PositionState(4, 10, 2))
    self.assertEqual(pos_3, PositionState(6, 15, 3))

  def testCalc_withTwoStateFnAndIndex1_usesSecondFunction(self):
    movement_pb = text_format.Parse("""
        state_fn {
          cartesian {
            x: "t"
            y: "0"
            angle: "0"
          }
        }
        lifetime: 5

        state_fn {
          cartesian {
            x: "0"
            y: "t"
            angle: "0"
          }
        }
        lifetime: 5
      """,
      spawner_pb2.Movement())
    movement = entity.Movement(movement_pb)
    movement.current_idx = 1
    movement.current_time = 0
    
    pos = movement.Calc({}, 3)

    self.assertEqual(pos, PositionState(0, 3, 0))

  def testCalc_transitionTime_storesFinalStateAndReturnsNext(self):
    movement_pb = text_format.Parse("""
        state_fn {
          cartesian {
            x: "t"
            y: "0"
            angle: "0"
          }
        }
        lifetime: 5

        state_fn {
          cartesian {
            x: "0"
            y: "t"
            angle: "0"
          }
        }
        lifetime: 5
      """,
      spawner_pb2.Movement())
    movement = entity.Movement(movement_pb)
    movement.current_idx = 0
    movement.current_time = 4
    
    pos = movement.Calc({}, 2)
    transition_pos = movement.GetAndClearTransitionPosition()

    self.assertEqual(movement.current_idx, 1)
    self.assertEqual(movement.current_time, 1)
    # Position at t = 6 - 5 (1.0s)
    self.assertEqual(pos, PositionState(0, 1, 0))
    # Position at t = lifetime (5.0s)
    self.assertEqual(transition_pos, PositionState(5, 0, 0))

  def testCalc_transitionBeyondLifetime_returnsNoneAndSetsActiveFalse(self):
    movement_pb = text_format.Parse("""
        state_fn {
          cartesian {
            x: "2 * t"
            y: "5 * t"
            angle: "t"
          }
        }
        lifetime: 5
        loop: false
      """,
      spawner_pb2.Movement())
    movement = entity.Movement(movement_pb)
    movement.current_time = 4.5

    pos = movement.Calc({}, 1)

    self.assertIsNone(pos)
    self.assertFalse(movement.is_active)

  def testCalc_transitionBeyondLifetimeLoop_returnsFirstMovementValue(self):
    movement_pb = text_format.Parse("""
        state_fn {
          cartesian {
            x: "t"
            y: "0"
            angle: "0"
          }
        }
        lifetime: 5

        state_fn {
          cartesian {
            x: "0"
            y: "t"
            angle: "0"
          }
        }
        lifetime: 5

        loop: true
      """,
      spawner_pb2.Movement())
    movement = entity.Movement(movement_pb)
    movement.current_idx = 1
    movement.current_time = 4
    
    pos = movement.Calc({}, 2)
    transition_pos = movement.GetAndClearTransitionPosition()

    self.assertAlmostEqual(movement.current_idx, 0)
    self.assertAlmostEqual(movement.current_time, 1)
    self.assertEqual(pos, PositionState(1, 0, 0))
    self.assertEqual(transition_pos, PositionState(0, 5, 0))

class TestEntity(unittest.TestCase):
  GenerateCartesianStateFn(text_format.Parse("""
      id { id: 'x_and_angle_move' }
      x: "2 * t"
      angle: "pi * t"
    """, spawner_pb2.CartesianStateFn()), True)
  GenerateCartesianStateFn(text_format.Parse("""
      id { id: 'y_move' }
      y: "5 * t"
    """, spawner_pb2.CartesianStateFn()), True)

  GenerateCartesianStateFn(text_format.Parse("""
      id { id: 'y_reverse_move' }
      y: "-5 * t"
    """, spawner_pb2.CartesianStateFn()), True)

  def setUp(self):
    self.parent_entity_pb = text_format.Parse("""
        image: 'parent.png'

        movement {
          state_fn {
            id { id: 'x_and_angle_move'}
          }
          lifetime: 0
        }
      """, spawner_pb2.Entity())
    self.parent_entity = entity.Entity(self.parent_entity_pb)

    self.child_entity_pb = text_format.Parse("""
        image: 'child.png'

        movement {
          state_fn {
            id { id: 'y_move'}
          }
          lifetime: 6.0

          state_fn {
            id { id: 'y_reverse_move'}
          }
          lifetime: 6.0
          loop: true
        }
      """, spawner_pb2.Entity())

    self.child_entity = entity.Entity(
      self.child_entity_pb,
      self.parent_entity)
    self.parent_entity.AddChild(self.child_entity)

  def testSave_withoutName_raisesException(self):
    with self.assertRaises(Exception):
      entity.Entity.Save(self.child_entity_pb)

  def testInit_saveWithName_canBeAccessedLater(self):
    entity_id = 'entity_id'
    self.child_entity_pb.id.id = entity_id
    second_child_pb = spawner_pb2.Entity()
    second_child_pb.id.id = entity_id

    entity.Entity.Save(self.child_entity_pb)

    first_entity = entity.Entity(self.child_entity_pb)
    second_entity = entity.Entity(second_child_pb)

    self.assertEqual(first_entity.image, second_entity.image)

  def testUpdate_updateParentNoFollow_updatesChild(self):
    child_t0 = self.child_entity.AbsolutePosition()
    parent_t0 = self.parent_entity.AbsolutePosition()
    self.assertEqual(parent_t0, PositionState(0, 0, 0))
    self.assertEqual(child_t0, PositionState(0, 0, 0))
    
    self.parent_entity.Update({}, dt=1)

    child_t1 = self.child_entity.AbsolutePosition()
    parent_t1 = self.parent_entity.AbsolutePosition()
    self.assertEqual(child_t1, PositionState(0, 5, 0))
    self.assertEqual(parent_t1, PositionState(2, 0, math.pi))

  def test_withOffset_changesChildAbsolutePosition(self):
    self.child_entity.offset = PositionState(10, 0, 0)
    
    self.parent_entity.Update({}, dt=1)

    child_t1 = self.child_entity.AbsolutePosition()
    parent_t1 = self.parent_entity.AbsolutePosition()
    self.assertEqual(child_t1, PositionState(10, 5, 0))
    self.assertEqual(parent_t1, PositionState(2, 0, math.pi))

  def test_followCenter_addsParentAndChildAbsolutePosition(self):
    self.child_entity.follow_center = True
    
    self.parent_entity.Update({}, dt=1)

    child_t1 = self.child_entity.AbsolutePosition()
    parent_t1 = self.parent_entity.AbsolutePosition()
    self.assertEqual(child_t1, PositionState(2, 5, 0))
    self.assertEqual(parent_t1, PositionState(2, 0, math.pi))

  def test_followCenterAndAngle_rotatesChildPosition(self):
    self.child_entity.follow_center = True
    self.child_entity.follow_angle = True
    
    self.parent_entity.Update({}, dt=1)

    child_t1 = self.child_entity.AbsolutePosition()
    parent_t1 = self.parent_entity.AbsolutePosition()
    self.assertEqual(child_t1, PositionState(2, -5, math.pi))
    self.assertEqual(parent_t1, PositionState(2, 0, math.pi))

  def test_followAngle_rotatesChildAngle(self):
    self.child_entity.follow_center = False
    self.child_entity.follow_angle = True
    
    self.parent_entity.Update({}, dt=1)

    child_t1 = self.child_entity.AbsolutePosition()
    parent_t1 = self.parent_entity.AbsolutePosition()
    near_0 = 6.123233995736766e-16
    self.assertEqual(child_t1, PositionState(near_0, -5, math.pi))
    self.assertEqual(parent_t1, PositionState(2, 0, math.pi))


class TestSpawner(unittest.TestCase):
  def setUp(self):
    self.entity_pb = text_format.Parse("""
        id { id: "spawn_entity" }
        image: "imagination.png"
        scale: 1.0

        movement {
          state_fn {cartesian { x: "2 * t" }}
          lifetime: 0
        }
      """, spawner_pb2.Entity())
    entity.Entity.Save(self.entity_pb)
    self.entity = entity.Entity(self.entity_pb)

    self.parent_entity_pb = text_format.Parse("""
        id { id: "parent_entity" }
        image: "imagination.png"
        scale: 1.0

        movement {
          state_fn { cartesian { y: "t" } }
          lifetime: 0
        }
      """, spawner_pb2.Entity())
    self.parent_entity = entity.Entity(self.parent_entity_pb)

    entity.Entity.ZA_WARUDO.children_.clear()

  def testInit_createsOrderedSpawnTimes(self):
    spawner_pb = text_format.Parse("""
        spawn_entity { id { id: "spawn_entity" } }

        spawn_count: 5

        spawn_time_fn: "[0.1, 0, 0.4, 0.3, 0.2][idx]"

        period: 0
      """, spawner_pb2.Spawner())

    spawner = entity.Spawner(spawner_pb)

    expected_zipped_times = [
      (0  , 1),
      (0.1, 0),
      (0.2, 4),
      (0.3, 3),
      (0.4, 2),
    ]
    self.assertEqual(len(spawner.zipped_spawn_times_idx), 5)
    for i in range(5):
      self.assertEqual(spawner.zipped_spawn_times_idx[i], expected_zipped_times[i])

  def testUpdate_noThresholdChange_spawnsNothing(self):
    spawner_pb = text_format.Parse("""
        spawn_entity { id { id: "spawn_entity" } }
        spawn_count: 1
        spawn_time_fn: "5"
        period: 0
      """, spawner_pb2.Spawner())
    parent_pb = self.parent_entity_pb
    parent_pb.spawner.append(spawner_pb)
    parent = entity.Entity(parent_pb)

    parent.Update({}, 1)
    self.assertEqual(len(parent.children_), 0)

  def testUpdate_singleThreshold_spawnsOneEntity(self):
    spawner_pb = text_format.Parse("""
        spawn_entity { id { id: "spawn_entity" } }
        spawn_count: 1
        spawn_time_fn: "5"
        period: 0
      """, spawner_pb2.Spawner())

    parent_pb = self.parent_entity_pb
    parent_pb.spawner.append(spawner_pb)
    parent = entity.Entity(parent_pb)

    parent.Update({}, 4)
    self.assertEqual(len(entity.Entity.ZA_WARUDO.children_), 0)
    parent.Update({}, 2)
    self.assertEqual(len(entity.Entity.ZA_WARUDO.children_), 1)

  def testUpdate_multipleThresholds_spawnsMultipleEntities(self):
    spawner_pb = text_format.Parse("""
        spawn_entity { id { id: "spawn_entity" } }
        spawn_count: 2
        spawn_time_fn: "5 + idx"
        period: 0
      """, spawner_pb2.Spawner())
    parent_pb = self.parent_entity_pb
    parent_pb.spawner.append(spawner_pb)
    parent = entity.Entity(parent_pb)

    parent.Update({}, 4)
    self.assertEqual(len(entity.Entity.ZA_WARUDO.children_), 0)
    parent.Update({}, 3)
    self.assertEqual(len(entity.Entity.ZA_WARUDO.children_), 2)

  def testUpdate_passedPeriod_resetsSpawnPosAndTime(self):
    spawner_pb = text_format.Parse("""
        spawn_entity { id: { id: 'spawn_entity' } }
        spawn_count: 0
        spawn_time_fn: "5"
        period: 7
      """, spawner_pb2.Spawner())
    parent_pb = self.parent_entity_pb
    parent_pb.spawner.append(spawner_pb)
    parent = entity.Entity(parent_pb)

    parent.Update({}, 6.9)
    parent.Update({}, 0.11)
    self.assertAlmostEqual(parent.spawners[0].current_time, 0.01)
    self.assertEqual(parent.spawners[0].current_spawn_pos, 0)

if __name__ == '__main__':
  unittest.main()
