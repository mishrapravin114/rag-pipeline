import { Users, UserCheck, UserX, Shield, User, Eye } from 'lucide-react';

interface UserAnalyticsProps {
  data: {
    total_users: number;
    active_users: number;
    inactive_users: number;
    role_distribution: Record<string, number>;
    recent_registrations: number;
    active_last_30_days: number;
    generated_at: string;
  };
}

export function UserAnalytics({ data }: UserAnalyticsProps) {
  const getRoleIcon = (role: string) => {
    switch (role) {
      case 'admin':
        return <Shield className="h-4 w-4 text-purple-600" />;
      case 'user':
        return <User className="h-4 w-4 text-blue-600" />;
      case 'viewer':
        return <Eye className="h-4 w-4 text-green-600" />;
      default:
        return <User className="h-4 w-4 text-gray-600" />;
    }
  };

  const getRoleColor = (role: string) => {
    switch (role) {
      case 'admin':
        return 'text-purple-600 bg-purple-50 border-purple-200';
      case 'user':
        return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'viewer':
        return 'text-green-600 bg-green-50 border-green-200';
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  return (
    <div className="space-y-6">
      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Total Users */}
        <div className="bg-white p-6 rounded-lg border shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Total Users</p>
              <p className="text-3xl font-bold text-gray-900">{data.total_users}</p>
            </div>
            <div className="p-3 bg-blue-50 rounded-full">
              <Users className="h-6 w-6 text-blue-600" />
            </div>
          </div>
        </div>

        {/* Active Users */}
        <div className="bg-white p-6 rounded-lg border shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Active Users</p>
              <p className="text-3xl font-bold text-green-600">{data.active_users}</p>
              <p className="text-xs text-gray-500 mt-1">
                {data.total_users > 0 ? Math.round((data.active_users / data.total_users) * 100) : 0}% of total
              </p>
            </div>
            <div className="p-3 bg-green-50 rounded-full">
              <UserCheck className="h-6 w-6 text-green-600" />
            </div>
          </div>
        </div>

        {/* Inactive Users */}
        <div className="bg-white p-6 rounded-lg border shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Inactive Users</p>
              <p className="text-3xl font-bold text-red-600">{data.inactive_users}</p>
              <p className="text-xs text-gray-500 mt-1">
                {data.total_users > 0 ? Math.round((data.inactive_users / data.total_users) * 100) : 0}% of total
              </p>
            </div>
            <div className="p-3 bg-red-50 rounded-full">
              <UserX className="h-6 w-6 text-red-600" />
            </div>
          </div>
        </div>

        {/* Recent History */}
        <div className="bg-white p-6 rounded-lg border shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Active (30 days)</p>
              <p className="text-3xl font-bold text-blue-600">{data.active_last_30_days}</p>
              <p className="text-xs text-gray-500 mt-1">
                {data.recent_registrations} new this week
              </p>
            </div>
            <div className="p-3 bg-blue-50 rounded-full">
              <UserCheck className="h-6 w-6 text-blue-600" />
            </div>
          </div>
        </div>
      </div>

      {/* Role Distribution */}
      <div className="bg-white p-6 rounded-lg border shadow-sm">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Role Distribution</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(data.role_distribution).map(([role, count]) => (
            <div 
              key={role}
              className={`p-4 rounded-lg border ${getRoleColor(role)}`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {getRoleIcon(role)}
                  <span className="font-medium capitalize">{role}</span>
                </div>
                <span className="text-2xl font-bold">{count}</span>
              </div>
              <div className="mt-2">
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className={`h-2 rounded-full ${
                      role === 'admin' ? 'bg-purple-600' : 
                      role === 'user' ? 'bg-blue-600' : 'bg-green-600'
                    }`}
                    style={{ 
                      width: `${data.total_users > 0 ? (count / data.total_users) * 100 : 0}%` 
                    }}
                  ></div>
                </div>
                <p className="text-xs mt-1">
                  {data.total_users > 0 ? Math.round((count / data.total_users) * 100) : 0}% of users
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Data Timestamp */}
      <div className="text-xs text-gray-500 text-center">
        Last updated: {new Date(data.generated_at).toLocaleString()}
      </div>
    </div>
  );
} 