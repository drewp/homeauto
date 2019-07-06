JOB=collector
PORT=9072

TAG=bang6:5000/${JOB}_x86:latest

build_image:
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile *.py req* *.ini ../../stubs tmp_ctx
	docker build --network=host -t ${TAG} tmp_ctx

push_image: build_image
	docker push ${TAG}

shell: build_image
	docker run --rm -it --cap-add SYS_PTRACE \
	  --name=$(JOB)_shell \
	  --net=host \
	  -v `pwd`/.mypy_cache:/opt/.mypy_cache \
	  -v `pwd`/sse_collector.py:/opt/sse_collector.py \
	  ${TAG} /bin/bash

local_run: build_image
	docker run --rm -it -p ${PORT}:${PORT} \
	  --name=$(JOB)_local \
          --net=host \
          ${TAG} \
          python3 sse_collector.py -v

local_run_strace: build_image
	docker run --rm -it -p ${PORT}:${PORT} \
	  --name=$(JOB)_local \
          --net=host \
          --cap-add SYS_PTRACE \
          ${TAG} \
          strace -f -tts 200 python3 /mnt/sse_collector.py -v

local_run_pyspy: build_image
	docker run --rm -it -p ${PORT}:${PORT} \
	  --name=$(JOB)_local \
          --net=host \
          --cap-add SYS_PTRACE \
          ${TAG} \
          py-spy -- python3 sse_collector.py

typecheck: build_image
	docker run --rm -it -p ${PORT}:${PORT} \
	  --name=$(JOB)_mypy \
          --net=host \
	  -v `pwd`/.mypy_cache:/opt/.mypy_cache \
          ${TAG} \
           /usr/local/bin/mypy -m sse_collector -m export_to_influxdb -m logsetup -m patchablegraph -m patchsource -m rdfdb.patch


redeploy: push_image
	supervisorctl restart sse_collector_9072

