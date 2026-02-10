const keywords = [
  { text: 'SELECT', top: '8%', left: '5%', duration: '7s', delay: '0s' },
  { text: 'JOIN', top: '18%', right: '8%', duration: '6s', delay: '1s' },
  { text: 'WHERE', bottom: '25%', left: '10%', duration: '8s', delay: '0.5s' },
  { text: 'INSERT', top: '55%', right: '5%', duration: '7s', delay: '2s' },
  { text: 'GROUP BY', bottom: '10%', right: '15%', duration: '6s', delay: '1.5s' },
  { text: 'ORDER BY', top: '35%', left: '3%', duration: '8s', delay: '0.8s' },
  { text: 'UPDATE', bottom: '40%', right: '3%', duration: '7.5s', delay: '0.3s' },
  { text: 'DELETE', top: '70%', left: '12%', duration: '6.5s', delay: '1.8s' },
  { text: 'CREATE', top: '5%', right: '25%', duration: '8s', delay: '2.5s' },
  { text: 'ALTER', bottom: '5%', left: '30%', duration: '7s', delay: '1.2s' },
  { text: 'DROP', top: '45%', right: '20%', duration: '6s', delay: '0.7s' },
  { text: 'INDEX', bottom: '20%', left: '25%', duration: '7.5s', delay: '2.2s' },
];

export function FloatingKeywords() {
  return (
    <>
      {keywords.map((kw) => (
        <span
          key={kw.text}
          className="absolute text-primary/[0.07] font-mono text-sm font-bold select-none pointer-events-none"
          style={{
            top: kw.top,
            left: kw.left,
            right: kw.right,
            bottom: kw.bottom,
            animation: `${parseFloat(kw.duration) > 7 ? 'float-slow' : 'float-medium'} ${kw.duration} ease-in-out infinite`,
            animationDelay: kw.delay,
          }}
        >
          {kw.text}
        </span>
      ))}
    </>
  );
}
