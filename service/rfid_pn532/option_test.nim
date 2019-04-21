import options

type
  Base = ref object of RootObj
  A = ref object of Base
  B = ref object of Base
    opt: Option[A]

proc `==`(x: A, y: B): bool = false

proc initA(): A =
  new result

proc initB(): B =
  new result
  result.opt = none(A)
  echo "saved none"

let x = initB()
assert x.opt.isNone()
