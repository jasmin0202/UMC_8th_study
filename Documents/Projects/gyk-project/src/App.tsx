import { useState } from 'react'
import './App.css'

function App() {
  const [count, setCount] = useState<number>(0);
  const handleIncrement = () => setCount(count + 1);
  const handleDecrement = () => setCount(count - 1);

  return (
    <>
    <h1>{count}</h1>
    <button onClick={handleIncrement}>숫자 증가</button>
    <button onClick={handleDecrement}>숫자 감소</button>
    </>
  )
}

export default App
