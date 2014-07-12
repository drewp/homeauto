(function() {

  var style = document.createElement('style');
  style.type = 'text/css';
  var css = 'body.ew-resize, body.ew-resize * {cursor: ew-resize; user-select: none; -webkit-user-select: none; -moz-user-select: none; -ms-user-select: none;}\n';
  style.appendChild(document.createTextNode(css));
  document.getElementsByTagName('head')[0].appendChild(style);

  var validKeys = [46, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 189, 190, 37, 38, 39, 40, 8, 9];

  var oldValue, selection, range, rect;

  var delta = 0;
  var deltaStep = 5;
  var x = 0;
  var y = 0;
  var xOld = 0;

  Polymer({

    __doc__: {
      element: 'input-number',
      description: 'Input element for numeric data type.',
      status: 'alpha',
      url: 'https://github.com/arodic/input-number/',
      demo: 'http://arodic.github.com/input-number/',
      attributes: [
        { name: 'value', type: 'number', description: 'Input value.' },
        { name: 'min', type: 'number', description: 'Minimum value.' },
        { name: 'max', type: 'number', description: 'Maximum value.' },
        { name: 'step', type: 'number', description: 'Value increment when dragging in powers of 10.' },
        { name: 'toDeg', type: 'boolean', description: 'Converts displayed value to degrees.' },
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
    min: -Infinity,
    max: Infinity,
    step: -3,
    toDeg: false,
    editable: true,
    displayValue: 0,
    ready: function() {
      this.setAttribute('tabindex', 0);
      this.setAttribute('contenteditable', true);
      this.setAttribute('spellcheck', false);
      this.addEventListener('keydown', this.onKeydown.bind(this));
      this.addEventListener('focus', this.onFocus.bind(this));
      this.addEventListener('blur', this.onBlur.bind(this));

      // TODO: make better on mobile
      this.$.blocker.addEventListener('dblclick', this.onFocus.bind(this));
      this.$.blocker.addEventListener('contextmenu', this.onFocus.bind(this));
      this.$.blocker.addEventListener('mousedown', this.onStartDrag.bind(this));
      this.$.blocker.addEventListener('touchstart', this.onStartDrag.bind(this));

      this.addEventListener('keydown', this.onKeydown.bind(this));
      this.addEventListener('mouseover', this.updateBlocker.bind(this));

    },
    domReady: function() {
      this.stepChanged();
      this.displayValueChanged();
      this.updateBlocker();
    },
    onStartDrag: function(event) {
      // event.stopPropagation();
      event.preventDefault();
      event = event.changedTouches ? event.changedTouches[0] : event;

      document.body.classList.add('ew-resize');
      xOld = event.clientX;
      delta = 0;
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
      // event.stopPropagation();
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
      // event.stopPropagation();
      // TODO: add acceleration
      if (!this.editable) return;
      if (event.type == 'mousemove' && event.which === 0) {
        this._onEndDrag(event);
        return;
      }

      oldValue = this.value;

      event = event.changedTouches ? event.changedTouches[0] : event;

      x = event.clientX;
      y = event.clientY;
      delta += x - xOld;
      xOld = event.clientX;

      while (Math.abs(delta) > deltaStep) {
        if (delta > deltaStep) {
          if (this.toDeg) this.value += Math.pow(10, this.step) / 180 * Math.PI;
          else this.value += Math.pow(10, this.step);
          delta -= deltaStep;
        }
        if (delta < -deltaStep) {
          if (this.toDeg) this.value -= Math.pow(10, this.step) / 180 * Math.PI;
          else this.value -= Math.pow(10, this.step);
          delta += deltaStep;
        }
      }
      this.value = Math.max(this.value, this.min);
      this.value = Math.min(this.value, this.max);
      if (this.value != oldValue) this.fire('input-changed', { input: this, oldValue: oldValue, newValue: this.value, delta: this.value - oldValue });
    },

    onKeydown: function(event) {
      // TODO: number keyboard on mobile
      event.stopPropagation();
      if(event.which == 13) {
        selection = window.getSelection();
        selection.removeAllRanges();
        this.blur();
        return;
      }

      oldValue = this.value;

      if (!this.editable || validKeys.indexOf(event.which) == -1) {
        event.preventDefault();
        return;
      }
      setTimeout(function(){
        this.updateValue();
        this.fire('input-changed', { input: this, oldValue: oldValue, newValue: this.value, delta: this.value - oldValue });
      }.bind(this), 1);

    },
    onFocus: function(event) {
      event.preventDefault();
      selection = window.getSelection();
      selection.removeAllRanges();
      range = document.createRange();
      this.textContent = this.displayValue;
      range.selectNodeContents(this);
      selection.addRange(range);
      this.focused = true;
    },
    onBlur: function() {
      this.updateValue();
      selection = window.getSelection();
      selection.removeAllRanges();
      this.focused = false;
      this.updateValue();
      this.valueChanged();
      this._match = this.displayValue.toString().match(this.regEx);
      this.textContent = this._match ? parseFloat(this._match[1]) : this.displayValue;
    },
    updateValue: function() {
      if (!isNaN(this.textContent) && (this.textContent.slice(-1) != '.')) {
        if (this.toDeg)
          this.value = parseFloat(this.textContent) / 180 * Math.PI;
        else
          this.value = parseFloat(this.textContent);
      }
    },
    updateBlocker: function() {
      rect = this.getBoundingClientRect();
      this.$.blocker.style.width = rect.width + 'px';
      this.$.blocker.style.height = rect.height + 'px';
    },
    valueChanged: function() {
      if (this.value < this.min) this.min = this.value;
      if (this.value > this.max) this.max = this.value;

      if (!this.focused) {
        if (this.toDeg)
          this.displayValue = this.value / Math.PI * 180;
        else
          this.displayValue = this.value;
      }
    },
    displayValueChanged: function() {
      this._match = this.displayValue.toString().match(this.regEx);
      this.textContent = this._match ? parseFloat(this._match[1]) : this.displayValue;
      this.updateBlocker();
    },
    toDegChanged: function() {
      this.valueChanged();
    },
    minChanged: function() {
      this.value = Math.max(this.value, this.min);
    },
    maxChanged: function() {
      this.value = Math.min(this.value, this.max);
    },
    stepChanged: function() {
      if (this.step < 0) {
        this.regEx = new RegExp("(^-?\\d+\\.\\d{" + Math.abs(this.step) + "})(\\d)");
      } else {
        this.regEx = new RegExp("(^-?\\d+\\.\\d{" + 1 + "})(\\d)");
      }
    }
  });

})();
