FROM bang6:5000/base_x86

WORKDIR /opt

COPY browser_test_requirements.txt ./

RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r browser_test_requirements.txt
# not sure why this doesn't work from inside requirements.txt
RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -U 'https://github.com/drewp/cyclone/archive/python3.zip?v2'

COPY ./patchablegraph.py ./patchsource.py ./setup.py __init__.py patchablegraph/
RUN pip3 install patchablegraph/

COPY browser_test.py ./

EXPOSE 8021

CMD [ "python3", "browser_test.py" ]
