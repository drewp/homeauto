(function() {

  var style = document.createElement('style');
  style.type = 'text/css';
  var css = 'body.ew-resize, body.ew-resize * {cursor: ew-resize; user-select: none; -webkit-user-select: none; -moz-user-select: none; -ms-user-select: none;}\n';
  style.appendChild(document.createTextNode(css));
  document.getElementsByTagName('head')[0].appendChild(style);

  function linToLog(value) {
    var minv = Math.log(1);
    var maxv = Math.log(101);
    var scale = (maxv - minv);
    return (Math.exp(minv + scale * (value)) - 1) / 100;
  }

  function logToLin(value) {
    var minv = Math.log(1);
    var maxv = Math.log(101);
    var scale = (maxv - minv);
    return (Math.log(value * 100 + 1) - minv) / scale;
  }

  var rect, oldValue, val, displayValue;

  Polymer({

    __doc__: {
      element: 'input-slider',
      description: 'Input element for numeric data type.',
      status: 'alpha',
      url: 'https://github.com/arodic/input-slider/',
      demo: 'http://arodic.github.com/input-slider/',
      attributes: [
        { name: 'value', type: 'number', description: 'Input value.' },
        { name: 'min', type: 'number', description: 'Minimum value.' },
        { name: 'max', type: 'number', description: 'Maximum value.' },
        { name: 'log', type: 'boolean', description: 'Enables logarithmic scale.' },
        { name: 'editable', type: 'boolean', description: 'Determines if the input can be edited.' }
      ],
      properties: [],
      methods: [],
      events: [
        {
          name: 'input-changed',
          description: 'Fires when value attribute is changed.'
        }
      ]
    },

    value: 0,
    min: 0,
    max: 1,
    log: false,
    editable: true,
    observe: {'min max log': 'valueChanged'},
    ready: function() {
      this.addEventListener('mousedown', this.onStartDrag.bind(this));
      this.addEventListener('touchstart', this.onStartDrag.bind(this));
    },
    domReady: function() {
      this.valueChanged();
    },
    onStartDrag: function(event) {
      event.preventDefault();
      event.stopPropagation();

      rect = this.getBoundingClientRect();
      this.onDrag(event);

      event = event.changedTouches ? event.changedTouches[0] : event;

      if (!this.editable) return;

      document.body.classList.add('ew-resize');
      document.activeElement.blur();

      this._onDrag = this.onDrag.bind(this);
      this._onEndDrag = this.onEndDrag.bind(this);
      document.addEventListener('mousemove', this._onDrag, false);
      document.addEventListener('mouseup', this._onEndDrag, false);
      this.addEventListener('touchmove', this._onDrag, false);
      this.addEventListener('touchend', this._onEndDrag, false);
      this.addEventListener('touchcancel', this._onEndDrag, false);
      this.addEventListener('touchleave', this._onEndDrag, false);
    },
    onEndDrag: function(event) {
      event.preventDefault();
      event.stopPropagation();
      event = event.changedTouches ? event.changedTouches[0] : event;

      document.body.classList.remove('ew-resize');
      document.removeEventListener('mousemove', this._onDrag, false);
      document.removeEventListener('mouseup', this._onEndDrag, false);
      this.removeEventListener('touchmove', this._onDrag, false);
      this.removeEventListener('touchend', this._onEndDrag, false);
      this.removeEventListener('touchcancel', this._onEndDrag, false);
      this.removeEventListener('touchleave', this._onEndDrag, false);
    },
    onDrag: function(event) {
      event.preventDefault();
      event.stopPropagation();

      if (!this.editable) return;
      if (event.type == 'mousemove' && event.which === 0) {
        this._onEndDrag(event);
        return;
      }

      oldValue = this.value;

      event = event.changedTouches ? event.changedTouches[0] : event;

      val = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
      if (this.log) val = linToLog(val);
            
      this.value = this.min + (this.max - this.min) * val;
      if (this.value != oldValue) this.fire('input-changed', { input: this });

    },

    valueChanged: function() {
      if (this.value < this.min) this.min = this.value;
      if (this.value > this.max) this.max = this.value;

      displayValue = (this.value - this.min) / (this.max - this.min);
      if (this.log) this.$.value.style.width = logToLin(displayValue) * 100 + '%';
      else this.$.value.style.width = displayValue * 100 + '%';
    }
  });

})();
