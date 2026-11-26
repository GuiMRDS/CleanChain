import { useEffect, useState } from 'react';
import './HeroIntro.css';

function useTyped(text, speed = 32, delay = 500) {
  const [count, setCount] = useState(0);
  // Restart when the text changes (adjusted during render, as React recommends).
  const [textoVisto, setTextoVisto] = useState(text);
  if (text !== textoVisto) {
    setTextoVisto(text);
    setCount(0);
  }
  useEffect(() => {
    let id;
    const start = setTimeout(() => {
      id = setInterval(() => {
        setCount((c) => {
          if (c >= text.length) {
            clearInterval(id);
            return c;
          }
          return c + 1;
        });
      }, speed);
    }, delay);
    return () => {
      clearTimeout(start);
      clearInterval(id);
    };
  }, [text, speed, delay]);
  return text.slice(0, count);
}

export default function HeroIntro({ compact, greeting, titulo = 'Seu Windows,' }) {
  const typed = useTyped(greeting);

  return (
    <div className={`hero-intro${compact ? ' is-compact' : ''}`}>
      <h1 className="hero-title">
        {titulo}
        <br />
        <em>mais leve.</em>
      </h1>
      <p className="agent-line" aria-label={greeting}>
        <span className="agent-line__prompt">›</span>
        <span aria-hidden="true">{typed}</span>
        <span className="agent-line__caret" aria-hidden="true" />
      </p>
    </div>
  );
}
