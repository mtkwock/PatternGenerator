import math
import unittest
from proto import spawner_pb2
from google.protobuf import text_format

from src import state_function

SIMPLE_CONTEXT = {
  "x": 100,
  "y": 200,
  "o": math.pi,
  "t": 1.5,
  "dt": 0.016,
}

class TestMakeFn(unittest.TestCase):
  def test_withConstant_makesConstantExpression(self):
    expr = "42"
    res = state_function.MakeFn(expr)

    self.assertEqual(res(SIMPLE_CONTEXT), 42)

  def test_usingTime_variesOnTime(self):
    expr = "200 * t"
    res = state_function.MakeFn(expr)

    self.assertAlmostEqual(res(SIMPLE_CONTEXT), 300.0, 4)
    later = SIMPLE_CONTEXT.copy()
    later['t'] = 3.0
    self.assertAlmostEqual(res(later), 600.0, 4)

  def test_polarCoordinateExpression_handlesNicely(self):
    # r oscillates every 2 seconds with an amplitude of 10 and a mean of 100
    r = '100 + 10 * sin(pi * t)'
    theta = "t * pi / 4"
    expr = f"({r}) * cos({theta})"

    res = state_function.MakeFn(expr)

    times_and_xs = [
      (0.0, 100.0),
      (0.5, 101.62674857624154),
      (1.0, 70.71067811865476),
      (1.5, 34.44150891285808),
      (2.0, 0),
      (2.5, -42.09517756015987),
    ]
    for t, v in times_and_xs:
      ctx = SIMPLE_CONTEXT.copy()
      self.assertAlmostEqual(
        res({'t': t, 'sin': math.sin, 'pi': math.pi, 'cos': math.cos}),
        v,
        4)

  def test_usingInvalidVariable_throwsNameError(self):
    expr = "ttt"

    res = state_function.MakeFn(expr)
    
    with self.assertRaises(NameError):
      res({})

class TestGenerateCartesianStateFn(unittest.TestCase):
  def tearDown(self):
    state_function.ClearDefinedFunctions()

  def test_emptyCartesian_usesZeroDefaults(self):
    cartesian_pb = spawner_pb2.CartesianStateFn()

    res = state_function.GenerateCartesianStateFn(cartesian_pb)

    state = res.Calc({"t": 1})
    self.assertAlmostEqual(state.x, 0)
    self.assertAlmostEqual(state.y, 0)
    self.assertAlmostEqual(state.angle, 0)

  def test_parabolicFunction_isParabolic(self):
    cartesian_pb = spawner_pb2.CartesianStateFn()
    cartesian_pb.x = "10 * t"
    cartesian_pb.y = "10 * t ** 2"

    res = state_function.GenerateCartesianStateFn(cartesian_pb)

    time_1_state = res.Calc({"t": 1})
    self.assertAlmostEqual(time_1_state.x, 10)
    self.assertAlmostEqual(time_1_state.y, 10)
    self.assertAlmostEqual(time_1_state.angle, 0)

    time_2_state = res.Calc({"t": 2})
    self.assertAlmostEqual(time_2_state.x, 20)
    self.assertAlmostEqual(time_2_state.y, 40)
    self.assertAlmostEqual(time_2_state.angle, 0)

    time_3_state = res.Calc({"t": 3})
    self.assertAlmostEqual(time_3_state.x, 30)
    self.assertAlmostEqual(time_3_state.y, 90)
    self.assertAlmostEqual(time_3_state.angle, 0)

class TestGeneratePolarStateFn(unittest.TestCase):
  def tearDown(self):
    state_function.ClearDefinedFunctions()

  def test_interesingPolarFunction_calcsCorrectly(self):
    polar_pb = spawner_pb2.PolarStateFn()
    polar_pb.r = '100 + 10 * sin(pi * t)'
    polar_pb.theta = 't * pi / 4'

    res = state_function.GeneratePolarStateFn(polar_pb)

    times_and_xys = [
      (0.0, 100.0,                0),
      (0.5, 101.62674857624154,  42.095177560159875),
      (1.0,  70.71067811865476,  70.71067811865476),
      (1.5,  34.44150891285808,  83.1491579260158),
      (2.0,   0,                100.0),
      (2.5, -42.09517756015987, 101.62674857624154),
    ]
    for t, x, y in times_and_xys:
      state = res.Calc({'t': t})
      self.assertAlmostEqual(state.x, x, 4)
      self.assertAlmostEqual(state.y, y, 4)

class TestGenerateDeltaStateFn(unittest.TestCase):
  def tearDown(self):
    state_function.ClearDefinedFunctions()

  def test_simpleVelocity(self):
    delta_pb = spawner_pb2.DeltaStateFn()
    delta_pb.dx = "10"
    delta_pb.dy = "20"
    delta_pb.w = "1"

    res = state_function.GenerateDeltaStateFn(delta_pb)

    state = res.Calc({
      "x": 100,
      "y": -100,
      "angle": 0,
      "dt": 2
    })
    # 100 + 10 * 2
    self.assertAlmostEqual(state.x, 120)
    # -100 + 20 * 2
    self.assertAlmostEqual(state.y, -60)
    # 0 + 1 * 2
    self.assertAlmostEqual(state.angle, 2)

class TestGenerateCompiledStateFn(unittest.TestCase):
  def setUp(self):
    cartesian_pb = spawner_pb2.CartesianStateFn()
    cartesian_pb.id.id = "eidentiddies"
    cartesian_pb.x = "10 * t"
    cartesian_pb.y = "20 * t"
    cartesian_pb.angle = "pi"

    self.cartesian_pb_ = cartesian_pb

    self.existing_fn = state_function.GenerateCartesianStateFn(cartesian_pb, True)

  def test_usingExistingId_findsExistingFunction(self):
    state_fn = spawner_pb2.StateFn()
    # See setUp for this existing id.
    state_fn.id.id = "eidentiddies"

    res = state_function.GenerateCompiledStateFn(state_fn)

    self.assertEqual(res, self.existing_fn)

  def test_usingNonExistingId_throwsException(self):
    state_fn = spawner_pb2.StateFn()
    state_fn.id.id = "identities"

    with self.assertRaisesRegex(Exception, 'Expected predefined StateFn for id: .*'):
      state_function.GenerateCompiledStateFn(state_fn)

  def test_withoutSetFunction_throwsException(self):
    state_fn = spawner_pb2.StateFn()

    with self.assertRaisesRegex(Exception, "StateFn does not have any function set\\."):
      state_function.GenerateCompiledStateFn(state_fn)

  def test_withCartesian_generatesCompiledStateFn(self):
    state_fn = spawner_pb2.StateFn()
    state_fn.cartesian.MergeFrom(self.cartesian_pb_)
    res = state_function.GenerateCompiledStateFn(state_fn)

    state = res.Calc({'t': 2})

    self.assertEqual(state.x, 20)
    self.assertEqual(state.y, 40)
    self.assertAlmostEqual(state.angle, math.pi)

if __name__ == '__main__':
  unittest.main()
