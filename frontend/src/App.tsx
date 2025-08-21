import { useState } from 'react'
import HealthCheck from './components/HealthCheck'
import './App.css'

function App() {
  const [count, setCount] = useState(0)

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="container mx-auto px-4 py-8">
        <header className="text-center mb-8">
          <h1 className="text-4xl font-bold text-green-600 mb-2">
            ReplantWorld
          </h1>
          <p className="text-gray-600">
            Solana-based Carbon Credit NFT Platform
          </p>
        </header>

        <main className="max-w-4xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-2xl font-semibold mb-4">System Status</h2>
              <HealthCheck />
            </div>

            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-2xl font-semibold mb-4">Quick Actions</h2>
              <div className="space-y-4">
                <button 
                  className="w-full bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded"
                  onClick={() => setCount((count) => count + 1)}
                >
                  Test Counter: {count}
                </button>
                <button className="w-full bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded">
                  Connect Wallet
                </button>
                <button className="w-full bg-purple-500 hover:bg-purple-600 text-white font-bold py-2 px-4 rounded">
                  View NFTs
                </button>
              </div>
            </div>
          </div>

          <div className="mt-8 bg-white rounded-lg shadow-md p-6">
            <h2 className="text-2xl font-semibold mb-4">Development Environment</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="text-center p-4 bg-gray-50 rounded">
                <h3 className="font-semibold">Frontend</h3>
                <p className="text-sm text-gray-600">React + TypeScript + Vite</p>
              </div>
              <div className="text-center p-4 bg-gray-50 rounded">
                <h3 className="font-semibold">Backend</h3>
                <p className="text-sm text-gray-600">Django + PostgreSQL</p>
              </div>
              <div className="text-center p-4 bg-gray-50 rounded">
                <h3 className="font-semibold">Blockchain</h3>
                <p className="text-sm text-gray-600">Solana Devnet</p>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}

export default App
