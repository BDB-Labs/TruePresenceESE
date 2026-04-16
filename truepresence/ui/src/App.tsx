import React, { useState } from 'react';
import { Shield, Users, Lock, LayoutDashboard } from 'lucide-react';

const PrototypeUI = () => {
  const [tenant, setTenant] = useState('Default-Tenant');
  const [role, setRole] = useState('Admin');

  return (
    <<divdiv className="min-h-screen bg-slate-50 flex">
      {/* Sidebar */}
      <<asideaside className="w-64 bg-slate-900 text-white p-6 flex flex-col">
        <<divdiv className="text-2xl font-bold mb-10 flex items-center gap-2">
          <<ShieldShield className="text-blue-400" /> TruePresence
        </div>
        <<navnav className="flex-1 space-y-4">
          <<divdiv className="flex items-center gap-3 p-2 bg-slate-800 rounded cursor-pointer">
            <<LayoutLayoutDashboard size={20} /> Dashboard
          </div>
          <div className="flex items-center gap-3 p-2 hover:bg-slate-800 rounded cursor-pointer transition">
            <<UsersUsers size={20} /> Tenants
          </div>
          <<divdiv className="flex items-center gap-3 p-2 hover:bg-slate-800 rounded cursor-pointer transition">
            <<LockLock size={20} /> Security
          </div>
        </nav>
        <<divdiv className="mt-auto p-4 bg-slate-800 rounded-lg text-xs">
          <<pp className="text-slate-400">Active Tenant</p>
          <<pp className="font-mono">{tenant}</p>
        </div>
      </aside>

      {/* Main Content */}
      <<mainmain className="flex-1 p-10">
        <<headerheader className="flex justify-between items-center mb-10">
          <<hh1 className="text-3xl font-bold text-slate-800">Role-Based Access Control</h1>
          <<divdiv className="flex gap-4 items-center">
            <<selectselect 
              value={tenant} 
              onChange={(e) => setTenant(e.target.value)}
              className="p-2 border rounded bg-white text-sm"
            >
              <<optionoption value="Default-Tenant">Default Tenant</option>
              <<optionoption value="Enterprise-A">Enterprise A</option>
              <<optionoption value="Gov-Secure">Gov Secure</option>
            </select>
            <<selectselect 
              value={role} 
              onChange={(e) => setRole(e.target.value)}
              className="p-2 border rounded bg-white text-sm"
            >
              <<optionoption value="Admin">Admin</option>
              <<optionoption value="Manager">Manager</option>
              <<optionoption value="User">User</option>
            </select>
          </div>
        </header>

        <<divdiv className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <<CardCard title="Tenant Settings" roleRequired="Admin" userRole={role} />
          <<CardCard title="User Management" roleRequired="Manager" userRole={role} />
          <<CardCard title="System Logs" roleRequired="User" userRole={role} />
        </div>
      </main>
    </div>
  );
};

const Card = ({ title, roleRequired, userRole }) => {
  const isAllowed = 
    roleRequired === 'User' || 
    (roleRequired === 'Manager' && (userRole === 'Manager' || userRole === 'Admin')) ||
    (roleRequired === 'Admin' && userRole === 'Admin');

  return (
    <<divdiv className={`p-6 rounded-xl border-2 transition-all ${isAllowed ? 'bg-white border-blue-200 shadow-sm' : 'bg-slate-100 border-slate-200 opacity-60'}`}>
      <<hh3 className="text-lg font-semibold mb-2">{title}</h3>
      <<pp className="text-sm text-slate-500 mb-4">Minimum Role: {roleRequired}</p>
      {isAllowed ? (
        <<buttonbutton className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">Access Module</button>
      ) : (
        <<buttonbutton disabled className="px-4 py-2 bg-slate-300 text-slate-500 rounded text-sm cursor-not-allowed">Locked</button>
      )}
    </div>
  );
};

export default PrototypeUI;
