import { Component } from 'react';

// Error boundary around the decorative 3D scene: if three.js fails (no WebGL, GPU crash, model
// load error), the robot disappears and the rest of the app keeps working. Without it, an error
// in the scene would unmount the whole interface and leave a blank window.
export default class CenaSegura extends Component {
  constructor(props) {
    super(props);
    this.state = { falhou: false };
  }

  static getDerivedStateFromError() {
    return { falhou: true };
  }

  componentDidCatch(err) {
    console.warn('CleanChain: a cena 3D falhou e foi desligada.', err);
  }

  render() {
    return this.state.falhou ? null : this.props.children;
  }
}
