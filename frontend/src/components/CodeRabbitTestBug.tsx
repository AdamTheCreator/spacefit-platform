import { useEffect, useState } from 'react';

interface Props {
  label: string;
}

export function CodeRabbitTestBug({ label }: Props) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setCount(count + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div>
      <p>{label}: {count}</p>
    </div>
  );
}
