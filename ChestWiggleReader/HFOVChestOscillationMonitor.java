import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Activity, Play, Pause, RotateCcw, Filter } from 'lucide-react';

export default function HFOVMonitor() {
  const [isPaused, setIsPaused] = useState(false);
  const [showFiltered, setShowFiltered] = useState(true);
  const [dataWindow, setDataWindow] = useState(300);
  const [currentTime, setCurrentTime] = useState(0);
  const [stats, setStats] = useState({
    freq: 8.5,
    amplitude: 45.2,
    vibrationLevel: 28.7
  });

  // Generate realistic HFOV simulation data
  const generateData = (timeOffset) => {
    const data = [];
    const rawData = [];
    const filteredData = [];
    const fs = 100; // 100 Hz sampling
    const duration = dataWindow / fs;
    
    // HFOV parameters
    const hfovFreq = 8.5; // Hz (typical HFOV frequency)
    const hfovAmplitude = 0.04; // g's
    
    for (let i = 0; i < dataWindow; i++) {
      const t = (timeOffset + i) / fs;
      
      // Simulate chest wall oscillation with HFOV frequency
      const hfovSignal = hfovAmplitude * Math.sin(2 * Math.PI * hfovFreq * t);
      
      // Add breathing artifact (slow, ~0.3 Hz)
      const breathingSignal = 0.08 * Math.sin(2 * Math.PI * 0.3 * t);
      
      // Add heartbeat artifact (~1.2 Hz)
      const heartbeatSignal = 0.015 * Math.sin(2 * Math.PI * 1.2 * t);
      
      // Add random noise
      const noise = (Math.random() - 0.5) * 0.01;
      
      // Gravity component (assume Z-axis mostly affected)
      const gravity = 1.0;
      
      // Raw signals with all components
      const ax_raw = hfovSignal * 0.7 + breathingSignal * 0.5 + heartbeatSignal + noise;
      const ay_raw = hfovSignal * 0.5 + breathingSignal * 0.3 + heartbeatSignal * 0.8 + noise;
      const az_raw = hfovSignal * 0.9 + breathingSignal * 0.6 + heartbeatSignal * 0.5 + gravity + noise;
      
      // Simulated bandpass filtered signal (5-15 Hz passband)
      // This removes breathing (<5 Hz) and high-frequency noise (>15 Hz)
      const ax_filtered = hfovSignal * 0.7 + noise * 0.3;
      const ay_filtered = hfovSignal * 0.5 + noise * 0.3;
      const az_filtered = hfovSignal * 0.9 + noise * 0.3;
      
      // Calculate magnitudes
      const mag_raw = Math.sqrt(ax_raw*ax_raw + ay_raw*ay_raw + az_raw*az_raw);
      const mag_filtered = Math.sqrt(ax_filtered*ax_filtered + ay_filtered*ay_filtered + az_filtered*az_filtered);
      
      data.push({
        time: t.toFixed(2),
        ax_raw: ax_raw.toFixed(3),
        ay_raw: ay_raw.toFixed(3),
        az_raw: az_raw.toFixed(3),
        ax_filt: ax_filtered.toFixed(3),
        ay_filt: ay_filtered.toFixed(3),
        az_filt: az_filtered.toFixed(3),
        mag_raw: mag_raw.toFixed(3),
        mag_filt: mag_filtered.toFixed(3)
      });
      
      rawData.push({
        time: t.toFixed(2),
        vibration: (Math.abs(hfovSignal + breathingSignal + heartbeatSignal + noise) * 1000).toFixed(2)
      });
      
      filteredData.push({
        time: t.toFixed(2),
        vibration: (Math.abs(hfovSignal + noise * 0.3) * 1000).toFixed(2)
      });
    }
    
    return { data, rawData, filteredData };
  };

  const [simulatedData, setSimulatedData] = useState(() => generateData(0));

  useEffect(() => {
    if (isPaused) return;
    
    const interval = setInterval(() => {
      setCurrentTime(prev => {
        const newTime = prev + 10;
        const newData = generateData(newTime);
        setSimulatedData(newData);
        
        // Update stats with slight variations
        setStats({
          freq: (8.5 + (Math.random() - 0.5) * 0.3).toFixed(1),
          amplitude: (45 + (Math.random() - 0.5) * 5).toFixed(1),
          vibrationLevel: (28 + (Math.random() - 0.5) * 3).toFixed(1)
        });
        
        return newTime;
      });
    }, 100);
    
    return () => clearInterval(interval);
  }, [isPaused, dataWindow]);

  const handleReset = () => {
    setCurrentTime(0);
    setSimulatedData(generateData(0));
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <Activity className="w-8 h-8 text-indigo-600" />
              <div>
                <h1 className="text-2xl font-bold text-gray-800">HFOV Chest Oscillation Monitor</h1>
                <p className="text-sm text-gray-600">Real-time chest wall vibration analysis with bandpass filtering</p>
              </div>
            </div>
            <div className="px-4 py-2 bg-green-100 text-green-700 rounded-lg font-medium text-sm">
              Simulated Live Monitoring
            </div>
          </div>

          {/* Control Panel */}
          <div className="flex gap-3 mb-4 flex-wrap">
            <button
              onClick={() => setIsPaused(!isPaused)}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
            >
              {isPaused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
              {isPaused ? 'Resume' : 'Pause'}
            </button>
            <button
              onClick={handleReset}
              className="flex items-center gap-2 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition"
            >
              <RotateCcw className="w-4 h-4" />
              Reset
            </button>
            <button
              onClick={() => setShowFiltered(!showFiltered)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition ${
                showFiltered 
                  ? 'bg-purple-600 text-white hover:bg-purple-700' 
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              <Filter className="w-4 h-4" />
              {showFiltered ? 'Filtered (5-15 Hz)' : 'Raw Signal'}
            </button>
            <select
              value={dataWindow}
              onChange={(e) => setDataWindow(Number(e.target.value))}
              className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            >
              <option value={100}>1 second</option>
              <option value={300}>3 seconds</option>
              <option value={500}>5 seconds</option>
              <option value={1000}>10 seconds</option>
            </select>
          </div>

          {/* Stats Cards */}
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="bg-gradient-to-br from-blue-50 to-blue-100 p-4 rounded-lg border border-blue-200">
              <div className="text-sm font-medium text-blue-600 mb-1">HFOV Frequency</div>
              <div className="text-3xl font-bold text-blue-900">{stats.freq} Hz</div>
              <div className="text-xs text-blue-600 mt-1">Target: 3-15 Hz</div>
            </div>
            <div className="bg-gradient-to-br from-green-50 to-green-100 p-4 rounded-lg border border-green-200">
              <div className="text-sm font-medium text-green-600 mb-1">Peak Amplitude</div>
              <div className="text-3xl font-bold text-green-900">{stats.amplitude} mg</div>
              <div className="text-xs text-green-600 mt-1">Maximum vibration</div>
            </div>
            <div className="bg-gradient-to-br from-purple-50 to-purple-100 p-4 rounded-lg border border-purple-200">
              <div className="text-sm font-medium text-purple-600 mb-1">RMS Vibration</div>
              <div className="text-3xl font-bold text-purple-900">{stats.vibrationLevel} mg</div>
              <div className="text-xs text-purple-600 mt-1">Average intensity</div>
            </div>
          </div>
        </div>

        {/* Comparison: Before Filtering */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-3 h-3 bg-red-500 rounded-full"></div>
            <h2 className="text-xl font-bold text-gray-800">Before Filtering - Raw Accelerometer Data</h2>
          </div>
          <p className="text-sm text-gray-600 mb-4">
            Contains HFOV signal (8.5 Hz) + breathing artifact (0.3 Hz) + heartbeat (1.2 Hz) + noise
          </p>
          <ResponsiveContainer width="100%" height={350}>
            <LineChart data={simulatedData.data} margin={{ top: 5, right: 30, left: 50, bottom: 25 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="time" 
                label={{ value: 'Time (seconds)', position: 'insideBottom', offset: -10 }} 
              />
              <YAxis label={{ value: 'Acceleration (g)', angle: -90, position: 'insideLeft' }} />
              <Tooltip />
              <Legend wrapperStyle={{ paddingTop: '20px' }} />
              <Line type="monotone" dataKey="ax_raw" stroke="#ef4444" name="X-axis (raw)" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="ay_raw" stroke="#22c55e" name="Y-axis (raw)" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="az_raw" stroke="#3b82f6" name="Z-axis (raw)" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Comparison: After Filtering */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-3 h-3 bg-purple-600 rounded-full"></div>
            <h2 className="text-xl font-bold text-gray-800">After Bandpass Filter (5-15 Hz) - Clean HFOV Signal</h2>
          </div>
          <p className="text-sm text-gray-600 mb-4">
            Butterworth 4th order bandpass filter removes breathing and heartbeat artifacts, isolating HFOV oscillations
          </p>
          <ResponsiveContainer width="100%" height={350}>
            <LineChart data={simulatedData.data} margin={{ top: 5, right: 30, left: 50, bottom: 25 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="time" 
                label={{ value: 'Time (seconds)', position: 'insideBottom', offset: -10 }} 
              />
              <YAxis label={{ value: 'Acceleration (g)', angle: -90, position: 'insideLeft' }} />
              <Tooltip />
              <Legend wrapperStyle={{ paddingTop: '20px' }} />
              <Line type="monotone" dataKey="ax_filt" stroke="#dc2626" name="X-axis (filtered)" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="ay_filt" stroke="#16a34a" name="Y-axis (filtered)" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="az_filt" stroke="#2563eb" name="Z-axis (filtered)" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Vibration Magnitude Comparison */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          <h2 className="text-xl font-bold text-gray-800 mb-4">Vibration Magnitude Comparison</h2>
          <p className="text-sm text-gray-600 mb-4">
            Notice how the filtered signal has clear, regular oscillations at HFOV frequency without low-frequency drift
          </p>
          <ResponsiveContainer width="100%" height={350}>
            <LineChart data={simulatedData.rawData} margin={{ top: 5, right: 30, left: 50, bottom: 25 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="time" 
                label={{ value: 'Time (seconds)', position: 'insideBottom', offset: -10 }} 
              />
              <YAxis label={{ value: 'Vibration (millig)', angle: -90, position: 'insideLeft' }} />
              <Tooltip />
              <Legend wrapperStyle={{ paddingTop: '20px' }} />
              <Line 
                type="monotone" 
                dataKey="vibration" 
                stroke="#94a3b8" 
                name="Raw (unfiltered)" 
                dot={false} 
                strokeWidth={2}
                opacity={0.6}
              />
              <Line 
                type="monotone" 
                data={simulatedData.filteredData}
                dataKey="vibration" 
                stroke="#8b5cf6" 
                name="Filtered (5-15 Hz)" 
                dot={false} 
                strokeWidth={2.5}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Filter Information */}
        <div className="bg-purple-50 border border-purple-200 rounded-xl p-6">
          <h3 className="text-lg font-bold text-purple-900 mb-3 flex items-center gap-2">
            <Filter className="w-5 h-5" />
            Butterworth Bandpass Filter (5-15 Hz)
          </h3>
          <div className="grid md:grid-cols-2 gap-4 text-sm text-purple-800">
            <div>
              <p className="font-semibold mb-2">Filter Parameters:</p>
              <ul className="list-disc list-inside space-y-1">
                <li>Low cutoff: 5 Hz (removes breathing, 0.2-0.5 Hz)</li>
                <li>High cutoff: 15 Hz (removes high-frequency noise)</li>
                <li>Order: 4th order (steep rolloff)</li>
                <li>Sampling rate: 100 Hz (Nyquist: 50 Hz)</li>
              </ul>
            </div>
            <div>
              <p className="font-semibold mb-2">What It Removes:</p>
              <ul className="list-disc list-inside space-y-1">
                <li>Breathing artifacts (0.2-0.5 Hz)</li>
                <li>Body movements (0-1 Hz)</li>
                <li>Heartbeat harmonics (1-3 Hz)</li>
                <li>High-frequency sensor noise (&gt;15 Hz)</li>
              </ul>
            </div>
          </div>
          <div className="mt-4 p-3 bg-white rounded-lg">
            <p className="text-sm text-purple-900">
              <strong>Result:</strong> Clean 8.5 Hz oscillation signal corresponding to HFOV chest wall vibrations, 
              making it easy to detect when the ventilator is active and measure oscillation amplitude.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
