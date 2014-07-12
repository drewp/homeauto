Polymer({

  __doc__: {
    element: 'input-rgb',
    description: 'Input element for color data type.',
    status: 'alpha',
    url: 'https://github.com/arodic/input-rgb/',
    demo: 'http://arodic.github.com/input-rgb/',
    attributes: [
      { name: 'r', type: 'number', description: 'Red value.' },
      { name: 'g', type: 'number', description: 'Green value.' },
      { name: 'b', type: 'number', description: 'Blue value.' },
      { name: 'hex', type: 'string', description: 'Hexadecimal value of rgb components.' },
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

  r: 1,
  g: 1,
  b: 1,
  hex: '#ffffff',
  observe: {
    'r g b': 'updateHex'
  },
  ready: function() {
    this.setAttribute('horizontal', true);
    this.setAttribute('layout', true);
    this.shadowRoot.addEventListener('input-changed', this.onInputChanged.bind(this));
  },
  attached: function() {
    this.setSwatchSize();
    this.updateHex();
  },
  updateHex: function() {
    var hex = (this.r * 255) << 16 ^ (this.g * 255) << 8 ^ (this.b * 255) << 0;
    this.hex = '#' + ('000000' + hex.toString(16)).slice(- 6);
    this.$.swatch.style.background = this.hex;
  },
  onInputChanged: function(event) {
    event.stopPropagation();
    this.hold = true;
    setTimeout(function() { this.hold = false; }, 100);
    this.fire('input-changed', { input: this, component: event.detail.input.id.replace('_', '') });
  },
  hexChanged: function() {

    var hex = parseInt(this.hex.replace(/^#/, ''), 16);
    hex = hex.toString();

    hex = Math.floor(hex);
    if (!this.hold) this.fire('input-changed', { input: this });

    this.r = (hex >> 16 & 255) / 255;
    this.g = (hex >> 8 & 255) / 255;
    this.b = (hex & 255) / 255;

  },
  setSwatchSize: function() {
    var rect = this.$.swatch.getBoundingClientRect();
    this.$.swatch.style.width = rect.height + 'px';
    this.$.picker.style.width = rect.height + 'px';
    this.$.picker.style.height = rect.height + 'px';
  },
  editableChanged: function() {
    if (this.editable) this.$.picker.style.display = 'block';
    else this.$.picker.style.display = 'none';
  }
});
