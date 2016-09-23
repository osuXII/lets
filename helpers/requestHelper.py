import tornado
import tornado.web
import tornado.gen
from tornado.ioloop import IOLoop
import glob
from helpers import logHelper as log
import threading
import time

currentMilliseconds = lambda: int(round(time.time() * 1000))

class asyncRequestHandler(tornado.web.RequestHandler):
	"""
	Tornado asynchronous request handler
	create a class that extends this one (requestHelper.asyncRequestHandler)
	use asyncGet() and asyncPost() instad of get() and post().
	Done. I'm not kidding.
	"""
	@tornado.web.asynchronous
	@tornado.gen.engine
	def get(self, *args, **kwargs):
		try:
			st = currentMilliseconds()
			glob.busyThreads += 1
			yield tornado.gen.Task(runBackground, (self.asyncGet, tuple(args), dict(kwargs)))
		except Exception as e:
			yield tornado.gen.Task(self.captureException, exc_info=True)
		finally:
			et = currentMilliseconds()
			log.info(">>>>> {} REQUEST TIME: {} ms".format(self.request.path, et-st))
			glob.busyThreads -= 1
			if not self._finished:
				self.finish()

	@tornado.web.asynchronous
	@tornado.gen.engine
	def post(self, *args, **kwargs):
		try:
			st = currentMilliseconds()
			glob.busyThreads += 1
			yield tornado.gen.Task(runBackground, (self.asyncPost, tuple(args), dict(kwargs)))
		except Exception as e:
			yield tornado.gen.Task(self.captureException, exc_info=True)
		finally:
			et = currentMilliseconds()
			log.warning("{} REQUEST TIME: {} ms".format(self.request.path, et-st))
			glob.busyThreads -= 1
			if not self._finished:
				self.finish()

	def asyncGet(self, *args, **kwargs):
		self.send_error(405)
		self.finish()

	def asyncPost(self, *args, **kwargs):
		self.send_error(405)
		self.finish()

	def getRequestIP(self):
		realIP = self.request.headers.get("X-Forwarded-For") if glob.cloudflare == True else self.request.headers.get("X-Real-IP")
		if realIP != None:
			return realIP
		return self.request.remote_ip


def runBackground(data, callback):
	"""
	Run a function in the background.
	Used to handle multiple requests at the same time
	"""
	func, args, kwargs = data
	def _callback(result):
		IOLoop.instance().add_callback(lambda: callback(result))
	glob.pool.apply_async(func, args, kwargs, _callback)
	threading.Thread(target=checkPoolSaturation).start()

def checkPoolSaturation():
	"""
	Check the number of busy threads in connections pool.
	If the pool is 100% busy, log a message to sentry
	"""
	size = int(glob.conf.config["server"]["threads"])
	if glob.busyThreads >= size:
		msg = "Connections threads pool is saturated!"
		log.warning(msg)
		glob.application.sentry_client.captureMessage(msg, level="warning", extra={
			"workersBusy": glob.busyThreads,
			"workersTotal": size
		})


def checkArguments(arguments, requiredArguments):
	"""
	Check that every requiredArguments elements are in arguments

	arguments -- full argument list, from tornado
	requiredArguments -- required arguments list es: ["u", "ha"]
	handler -- handler string name to print in exception. Optional
	return -- True if all arguments are passed, none if not
	"""
	for i in requiredArguments:
		if i not in arguments:
			return False
	return True

def printArguments(t):
	"""
	Print passed arguments, for debug purposes

	t -- tornado object (self)
	"""
	msg = "ARGS::"
	for i in t.request.arguments:
		msg += "{}={}\r\n".format(i, t.get_argument(i))
	log.debug(msg)
