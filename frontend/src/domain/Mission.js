import { ATMOSPHERES, BODIES } from './constants';

/**
 * Mission conditions for both phases (cruise + surface). Immutable.
 */
export class Mission {
  static DEFAULTS = {
    body: 'moon', // key into BODIES
    atm: 'base', // surface atmosphere, key into ATMOSPHERES
    eva: 4, // EVA-prep periods (high O₂)
    stay: 30, // surface stay, days
    preVent: 'normal', // cruise ventilation: 'normal' | 'reduced'
    pad: 180, // cruise days
    confirmed: false,
  };

  constructor(props = {}) {
    Object.assign(this, Mission.DEFAULTS, props);
  }

  get atmosphere() {
    return ATMOSPHERES[this.atm];
  }
  get destination() {
    return BODIES[this.body];
  }

  with(key, value) {
    return new Mission({ ...this, [key]: value });
  }

  /** Everything that affects scoring (confirmation doesn't). */
  fingerprint() {
    const { confirmed, ...rest } = this; // eslint-disable-line no-unused-vars
    return JSON.stringify(rest);
  }
}
