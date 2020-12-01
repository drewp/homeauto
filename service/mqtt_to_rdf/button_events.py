"""given repeated RF codes for a button press, make interesting button events"""

import time
from typing import Any, Callable, List
from rx.core.typing import Disposable
from rx.core import Observable, typing
from rx.disposable import CompositeDisposable, SingleAssignmentDisposable, SerialDisposable
from rx.scheduler import TimeoutScheduler
from rdflib import Namespace
ROOM = Namespace('http://projects.bigasterisk.com/room/')


def button_events(min_hold_sec: float,
                  release_after_sec: float,
                  scheduler=typing.Scheduler) -> Callable[[Observable], Observable]:

    def op(source: Observable) -> Observable:

        def subscribe(observer, scheduler_=None) -> Disposable:
            _scheduler = scheduler or scheduler_ or TimeoutScheduler.singleton()
            cancelable = SerialDisposable()
            button_state = [None]

            press_time: List[float] = [0.]

            def set_state(state):
                button_state[0] = state
                observer.on_next(button_state[0])

            set_state(ROOM['notPressed'])

            def on_next(x: Any) -> None:
                now = time.time()
                if button_state[0] == ROOM['notPressed']:
                    set_state(ROOM['pressed'])
                    press_time[0] = now
                elif button_state[0] == ROOM['pressed']:
                    if now > press_time[0] + min_hold_sec:
                        set_state(ROOM['held'])  # should be pressed AND held
                elif button_state[0] == ROOM['held']:
                    pass
                else:
                    raise NotImplementedError(f'button_state={button_state}')

                d = SingleAssignmentDisposable()
                cancelable.disposable = d

                def action(scheduler, state=None) -> None:
                    if button_state[0] != ROOM['notPressed']:
                        set_state(ROOM['notPressed'])

                d.disposable = _scheduler.schedule_relative(release_after_sec, action)

            def on_error(exception: Exception) -> None:
                cancelable.dispose()
                observer.on_error(exception)

            def on_completed() -> None:
                raise NotImplementedError

            subscription = source.subscribe_(on_next, on_error, on_completed, scheduler=scheduler_)
            return CompositeDisposable(subscription, cancelable)

        return Observable(subscribe)

    return op
